# plan-P1-1,P3-3
"""search_by_oe 工具 handler：OE→SKU 检索 + miss 时 ERP 兜底（ADR-35）"""

import asyncio
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from qipei_agent.integration.kingdee import KingdeeClient
from qipei_agent.shared.db import OeMapping, Product
from qipei_agent.shared.errors import get_logger

logger = get_logger("oe_search")

LOOSE_MATCH_LABEL = "【宽松匹配，已剔除末尾后缀字母，请业务员复核】"
FALLBACK_LABEL = "【金蝶兜底】"


def _sort_key(sku: dict) -> tuple:
    """多 SKU 排序：原厂 OE 优先、REF 靠后、同类型 sku_code 升序"""
    oe_type = sku.get("oe_type", "")
    is_ref = 1 if oe_type == "REF" else 0
    return (is_ref, sku.get("sku_code", ""))


def search_by_oe(
    oe_normalized: str,
    loose: bool = False,
    db_session: Optional[Session] = None,
    kingdee_client: Optional[KingdeeClient] = None,
) -> dict:
    """OE→SKU 检索

    输入：oe_normalized（归一化 OE 号）、loose（是否宽松匹配）
    输出：{skus: [{sku_code, name, oe_raw, oe_type, label, image_url, fitments}]}
    """
    if db_session is None:
        raise ValueError("db_session is required")

    skus: list[dict] = []

    # ─── 主检索：MySQL oe_mapping（PIM 来源） ───
    if loose:
        # 宽松模式：匹配 oe_base（去末尾字母基号）
        stmt = select(OeMapping).where(OeMapping.oe_base == oe_normalized)
    else:
        # 精确模式：oe_normalized 全等
        stmt = select(OeMapping).where(OeMapping.oe_normalized == oe_normalized)

    rows = db_session.execute(stmt).scalars().all()

    if rows:
        # 批量获取 product 信息
        sku_codes = {r.sku_code for r in rows}
        products_stmt = select(Product).where(Product.sku_code.in_(sku_codes))
        products_result = db_session.execute(products_stmt).scalars().all()
        product_map = {p.sku_code: p for p in products_result}

        for row in rows:
            product = product_map.get(row.sku_code)
            label = LOOSE_MATCH_LABEL if loose else ""
            skus.append({
                "sku_code": row.sku_code,
                "name": product.name if product else "",
                "oe_raw": row.oe_raw,
                "oe_type": row.oe_type or "原厂",
                "label": label,
                "image_url": product.image_url if product else "",
                "fitments": [],  # 后续步骤填充
            })

        # 排序：原厂 OE 优先、REF 靠后、同类型 sku_code 升序
        skus.sort(key=_sort_key)

    # ─── miss 触发 ERP 兜底（ADR-35） ───
    if not skus and kingdee_client:
        fallback_result = asyncio.get_event_loop().run_until_complete(
            kingdee_client.query_oe_fallback(oe_normalized)
        )
        if fallback_result.get("is_success") and fallback_result.get("rows"):
            for row in fallback_result["rows"]:
                # 金蝶兜底结果字段映射
                skus.append({
                    "sku_code": str(row.get("FMATERIALID", "")),
                    "name": "",
                    "oe_raw": row.get("FOENO", ""),
                    "oe_type": row.get("FOETYPE", "原厂"),
                    "label": FALLBACK_LABEL,
                    "image_url": "",
                    "fitments": [],
                })

    return {"skus": skus}
