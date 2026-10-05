# plan-P1-1,P3-4
"""search_by_fitment 工具 handler：车型→SKU 检索（ADR-21）"""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.db import Fitment, OeMapping, Product
from qipei_agent.shared.errors import get_logger

logger = get_logger("fitment_search")


def _normalize_brand(brand: str) -> str:
    """品牌名标准化映射"""
    config = get_settings().brand_normalize_config
    return config.get(brand, brand)


def search_by_fitment(
    brand: str,
    series: str,
    model: str,
    year: Optional[int] = None,
    engine_code: Optional[str] = None,
    db_session: Optional[Session] = None,
) -> dict:
    """车型→SKU 检索

    输入：brand, series, model, year?, engine_code?
    输出：{skus: [{sku_code, name, oe_list, image_url}]}
    """
    if db_session is None:
        raise ValueError("db_session is required")

    # brand 经映射后精确匹配
    brand_normalized = _normalize_brand(brand)

    # 构建查询
    stmt = select(Fitment).where(
        Fitment.brand == brand_normalized,
        Fitment.series == series,
    )

    # model 精确匹配（忽略大小写/去空格）
    model_clean = model.strip().upper()
    stmt = stmt.where(func.upper(Fitment.model) == model_clean)

    # year 落区间
    if year is not None:
        stmt = stmt.where(
            (Fitment.year_start <= year) & (Fitment.year_end >= year)
        )

    # engine_code 可选
    if engine_code:
        stmt = stmt.where(Fitment.engine_code == engine_code)

    rows = db_session.execute(stmt).scalars().all()

    if not rows:
        return {"skus": []}

    # 批量获取 product 和 oe_mapping
    sku_codes = {r.sku_code for r in rows}
    products_stmt = select(Product).where(Product.sku_code.in_(sku_codes))
    products = db_session.execute(products_stmt).scalars().all()
    product_map = {p.sku_code: p for p in products}

    oe_stmt = select(OeMapping).where(OeMapping.sku_code.in_(sku_codes))
    oe_rows = db_session.execute(oe_stmt).scalars().all()
    oe_map: dict[str, list[dict]] = {}
    for oe in oe_rows:
        oe_map.setdefault(oe.sku_code, []).append({
            "oe_normalized": oe.oe_normalized,
            "oe_raw": oe.oe_raw,
            "oe_type": oe.oe_type or "原厂",
        })

    skus = []
    for row in rows:
        product = product_map.get(row.sku_code)
        skus.append({
            "sku_code": row.sku_code,
            "name": product.name if product else "",
            "oe_list": oe_map.get(row.sku_code, []),
            "image_url": product.image_url if product else "",
        })

    return {"skus": skus}
