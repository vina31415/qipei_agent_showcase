# plan-P1-1,P3-7
"""calc_lead_time 工具 handler：交期计算（ADR-17/27/37）"""

from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.db import Product, PurchaseOrder, Stock, SupplierMaterial, SupplierMonthMax
from qipei_agent.shared.errors import get_logger

logger = get_logger("lead_time")

DEFAULT_SPOT_DAYS = 1
DEFAULT_PROCUREMENT_DAYS = 15


def calc_lead_time(
    sku_code: str,
    quantity: int,
    db_session: Optional[Session] = None,
) -> dict:
    """交期计算

    输入：sku_code, quantity
    输出：{lead_time, split, supplier_note, risk_level, risk_hint, pos, alternatives}
    """
    if db_session is None:
        raise ValueError("db_session is required")

    app_config = get_settings().app_config
    spot_days = app_config.get("spot_lead_time", DEFAULT_SPOT_DAYS)
    procurement_days = app_config.get("procurement_cycle_default", DEFAULT_PROCUREMENT_DAYS)

    # 查 product 获取 lead_time_override / procurement_cycle
    product_stmt = select(Product).where(Product.sku_code == sku_code)
    product = db_session.execute(product_stmt).scalar_one_or_none()
    if product:
        if product.lead_time_override:
            spot_days = product.lead_time_override
        if product.procurement_cycle:
            procurement_days = product.procurement_cycle

    # 查库存
    stock_stmt = select(Stock).where(Stock.sku_code == sku_code)
    stock = db_session.execute(stock_stmt).scalar_one_or_none()
    on_hand = stock.on_hand if stock else 0

    split: list[dict] = []
    pos: list[dict] = []
    alternatives: list[dict] = []
    risk_level = "none"
    risk_hints: list[str] = []
    supplier_note = ""

    remaining = quantity

    # ─── 分支 1：现货 ───
    if on_hand > 0:
        spot_qty = min(on_hand, remaining)
        split.append({"segment": "现货", "qty": spot_qty, "lead_time": spot_days})
        remaining -= spot_qty

    if remaining <= 0:
        # 全现货
        return {
            "lead_time": spot_days,
            "split": split,
            "supplier_note": "",
            "risk_level": "none",
            "risk_hint": "",
            "pos": [],
            "alternatives": [],
        }

    # ─── 分支 2：在途 PO ───
    po_stmt = (
        select(PurchaseOrder)
        .where(PurchaseOrder.sku_code == sku_code)
        .order_by(PurchaseOrder.plan_arrival_date)
    )
    po_rows = db_session.execute(po_stmt).scalars().all()

    for po in po_rows:
        if remaining <= 0:
            break
        po_qty = po.not_receive_qty or 0
        if po_qty <= 0:
            continue
        take = min(po_qty, remaining)
        arrival = po.plan_arrival_date
        lead = _calc_days_to_arrival(arrival)
        split.append({"segment": "在途", "qty": take, "lead_time": lead, "arrival_date": arrival})
        pos.append({"supplier_id": po.supplier_id, "arrival_date": arrival, "qty": po_qty})
        remaining -= take

    if remaining <= 0:
        lead_time = max(s["lead_time"] for s in split)
        return {
            "lead_time": lead_time,
            "split": split,
            "supplier_note": "",
            "risk_level": "none",
            "risk_hint": "",
            "pos": pos,
            "alternatives": [],
        }

    # ─── 分支 3：采购 ───
    # 供应商交期
    sm_stmt = select(SupplierMaterial).where(SupplierMaterial.sku_code == sku_code)
    sm_rows = db_session.execute(sm_stmt).scalars().all()

    default_supplier = None
    shortest_supplier = None
    shortest_lead = procurement_days

    for sm in sm_rows:
        if sm.is_default:
            default_supplier = sm
        if sm.lead_time_supp and sm.lead_time_supp < shortest_lead:
            shortest_lead = sm.lead_time_supp
            shortest_supplier = sm

    supplier = default_supplier or shortest_supplier
    lead = supplier.lead_time_supp if supplier else procurement_days

    if supplier and not supplier.is_default:
        risk_level = "medium"
        risk_hints.append("非默认供应商")
        supplier_note = "非默认供应商"

    split.append({"segment": "采购", "qty": remaining, "lead_time": lead})

    # 备选供应商
    for sm in sm_rows:
        if sm != supplier:
            alternatives.append({
                "supplier_id": sm.supplier_id,
                "lead_time": sm.lead_time_supp,
                "is_default": sm.is_default,
            })

    # ─── 风险评估 ───
    smm_stmt = select(SupplierMonthMax).where(
        SupplierMonthMax.sku_code == sku_code,
        SupplierMonthMax.supplier_id == (supplier.supplier_id if supplier else ""),
    )
    smm = db_session.execute(smm_stmt).scalar_one_or_none()
    if smm and smm.max_month_qty and quantity > smm.max_month_qty:
        risk_level = "high"
        risk_hints.append(f"需求量 {quantity} 超历史月最大供货 {smm.max_month_qty}")

    if lead > 30:
        risk_level = "high"
        risk_hints.append("长周期（>30天）")

    if not smm:
        if risk_level == "none":
            risk_level = "medium"
        risk_hints.append("无历史供货数据")

    lead_time = max(s["lead_time"] for s in split)
    return {
        "lead_time": lead_time,
        "split": split,
        "supplier_note": supplier_note,
        "risk_level": risk_level,
        "risk_hint": "; ".join(risk_hints) if risk_hints else "",
        "pos": pos,
        "alternatives": alternatives,
    }


def _calc_days_to_arrival(arrival_date: Optional[str]) -> int:
    """计算到到货日的天数"""
    if not arrival_date:
        return DEFAULT_PROCUREMENT_DAYS
    try:
        target = date.fromisoformat(arrival_date)
        delta = (target - date.today()).days
        return max(delta, 1)
    except (ValueError, TypeError):
        return DEFAULT_PROCUREMENT_DAYS
