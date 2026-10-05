# plan-P1-1,P2-4
"""ETL 装载：MySQL upsert（幂等，spec §3.4 / ADR-32）"""

from sqlalchemy import text
from sqlalchemy.orm import Session

from qipei_agent.shared.db import (
    Customer,
    Fitment,
    OeMapping,
    Price,
    Product,
    PurchaseOrder,
    Stock,
    SupplierMaterial,
    SupplierMonthMax,
)
from qipei_agent.shared.errors import get_logger

logger = get_logger(__name__)


def upsert_product(session: Session, record: dict) -> None:
    """upsert product 表（sku_code 主键）"""
    session.merge(Product(**record))


def upsert_oe_mapping(session: Session, record: dict) -> None:
    """upsert oe_mapping 表（sku_code + oe_normalized 联合唯一）"""
    # 先删除旧记录，再插入新记录（简单幂等策略）
    session.query(OeMapping).filter_by(
        sku_code=record["sku_code"],
        oe_normalized=record["oe_normalized"],
    ).delete()
    session.add(OeMapping(**record))


def upsert_fitment(session: Session, record: dict) -> None:
    """upsert fitment 表（sku_code + brand + series + model 联合唯一）"""
    session.query(Fitment).filter_by(
        sku_code=record["sku_code"],
        brand=record["brand"],
        series=record["series"],
        model=record["model"],
    ).delete()
    session.add(Fitment(**record))


def upsert_stock(session: Session, record: dict) -> None:
    """upsert stock 表（sku_code 主键）"""
    session.merge(Stock(**record))


def upsert_purchase_order(session: Session, record: dict) -> None:
    """upsert purchase_order 表"""
    session.add(PurchaseOrder(**record))


def upsert_supplier_material(session: Session, record: dict) -> None:
    """upsert supplier_material 表"""
    session.add(SupplierMaterial(**record))


def upsert_supplier_month_max(session: Session, record: dict) -> None:
    """upsert supplier_month_max 表"""
    session.query(SupplierMonthMax).filter_by(
        sku_code=record["sku_code"],
        supplier_id=record["supplier_id"],
    ).delete()
    session.add(SupplierMonthMax(**record))


def upsert_price(session: Session, record: dict) -> None:
    """upsert price 表"""
    session.add(Price(**record))


def upsert_customer(session: Session, record: dict) -> None:
    """upsert customer 表（customer_id 主键）"""
    session.merge(Customer(**record))


def truncate_table(session: Session, table_name: str) -> None:
    """清空表（全量同步前调用）"""
    session.execute(text(f"TRUNCATE TABLE {table_name}"))
    logger.info(f"已清空表 {table_name}")
