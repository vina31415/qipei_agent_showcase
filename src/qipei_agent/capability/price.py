# plan-P1-1,P3-6
"""get_price 工具 handler：分级价查询（ADR-26/34）"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.db import Customer, Price
from qipei_agent.shared.errors import E_NOT_FOUND, get_logger

logger = get_logger("price")


def _get_customer_tier(customer_id: str, db_session: Session) -> Optional[str]:
    """从 MySQL customer 表取 customer_tier"""
    stmt = select(Customer).where(Customer.customer_id == customer_id)
    row = db_session.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    tier = row.customer_tier
    if not tier:
        return None
    # 经 customer_level.yaml 映射
    config = get_settings().customer_level_config
    return config.get(tier, tier)


def get_price(
    sku_code: str,
    customer_id: str,
    quantity: int,
    db_session: Optional[Session] = None,
) -> dict:
    """分级价查询

    输入：sku_code, customer_id, quantity
    输出：{price, tax_included, original_price, currency, customer_tier, price_type, qty_range}
    """
    if db_session is None:
        raise ValueError("db_session is required")

    customer_tier = _get_customer_tier(customer_id, db_session)

    # ① 客户专属价
    stmt = select(Price).where(
        Price.sku_code == sku_code,
        Price.customer_id == customer_id,
    )
    rows = db_session.execute(stmt).scalars().all()
    if rows:
        matched = _match_tier(rows, quantity)
        if matched:
            return _build_result(matched, "专属价", customer_tier)

    # ② 等级价
    if customer_tier:
        stmt = select(Price).where(
            Price.sku_code == sku_code,
            Price.customer_id.is_(None),
            Price.customer_tier == customer_tier,
        )
        rows = db_session.execute(stmt).scalars().all()
        if rows:
            matched = _match_tier(rows, quantity)
            if matched:
                return _build_result(matched, "等级价", customer_tier)

    # ③ 人工询价（无 customer_id 或无等级价时）
    stmt = select(Price).where(
        Price.sku_code == sku_code,
        Price.customer_id.is_(None),
        Price.customer_tier.is_(None),
    )
    rows = db_session.execute(stmt).scalars().all()
    if rows:
        matched = _match_tier(rows, quantity)
        if matched:
            return _build_result(matched, "人工询价", customer_tier)

    raise ValueError(E_NOT_FOUND)


def _match_tier(rows: list, quantity: int) -> Optional[Price]:
    """按 quantity 命中阶梯区间"""
    # 按 qty_low 升序
    rows.sort(key=lambda r: r.qty_low or 0)
    matched = None
    for row in rows:
        qty_low = row.qty_low or 0
        qty_high = row.qty_high
        if qty_low <= quantity:
            if qty_high is None or quantity <= qty_high:
                return row
            matched = row  # 超上限取最大阶梯
    return matched


def _build_result(row: Price, price_type: str, customer_tier: Optional[str]) -> dict:
    """构建价格结果"""
    price = row.price
    is_include_tax = row.is_include_tax
    tax_rate = row.tax_rate or 0
    currency = row.currency or "CNY"

    # 含税/未税
    if is_include_tax:
        tax_included = True
        original_price = round(price / (1 + tax_rate / 100), 2) if tax_rate else price
    else:
        tax_included = False
        original_price = price

    return {
        "price": price,
        "tax_included": tax_included,
        "original_price": original_price,
        "currency": currency,
        "customer_tier": customer_tier,
        "price_type": price_type,
        "qty_range": {"low": row.qty_low, "high": row.qty_high},
    }
