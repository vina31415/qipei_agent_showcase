# plan-P2-1
"""SQLAlchemy 2.x 数据模型：产品主数据中心 10 表（spec §3.4）"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class Product(Base):
    """SKU 主数据（ETL 自 PIM）"""
    __tablename__ = "product"

    sku_code = Column(String(64), primary_key=True, comment="SKU 编码")
    name = Column(String(256), nullable=False, comment="品名")
    spec = Column(String(512), comment="规格")
    image_url = Column(String(1024), comment="图片 URL")
    material_group = Column(String(64), comment="物料组")
    is_sellable = Column(Boolean, default=True, comment="是否可售")
    lead_time_override = Column(Integer, comment="现货交期覆盖（天），空则取全局默认 1 天")
    procurement_cycle = Column(Integer, comment="采购周期 FLEADTIME（天），空则兜底 15 天")


class Customer(Base):
    """客户主数据（ETL 自 BD_CUSTOMER + BD_CUSTLEVEL）"""
    __tablename__ = "customer"

    customer_id = Column(String(64), primary_key=True, comment="客户内码 FCUSTID")
    name = Column(String(256), nullable=False, comment="客户名称")
    customer_tier = Column(String(8), comment="客户等级编码 A/B/C/D")
    currency = Column(String(8), default="CNY", comment="币种")


class OeMapping(Base):
    """OE 映射表（ETL 自 PIM，ADR-15）"""
    __tablename__ = "oe_mapping"
    __table_args__ = (
        Index("idx_oe_normalized", "oe_normalized"),
        Index("idx_oe_base", "oe_base"),
        Index("idx_oe_sku", "sku_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    oe_normalized = Column(String(128), nullable=False, comment="归一化后 OE 号（精确匹配）")
    oe_raw = Column(String(128), nullable=False, comment="原始 OE 号")
    oe_base = Column(String(128), comment="基号（去末尾字母，宽松匹配用）")
    oe_type = Column(String(16), default="原厂", comment="原厂 / REF")


class Fitment(Base):
    """车型适配表（ETL 自 PIM，ADR-21）"""
    __tablename__ = "fitment"
    __table_args__ = (
        Index("idx_fitment_brand_series", "brand", "series"),
        Index("idx_fitment_sku", "sku_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    brand = Column(String(32), nullable=False, comment="品牌（标准化编码）")
    series = Column(String(64), nullable=False, comment="车系")
    model = Column(String(128), nullable=False, comment="车型")
    engine_code = Column(String(64), comment="发动机代码")
    year_start = Column(Integer, comment="适配起始年份")
    year_end = Column(Integer, comment="适配结束年份")
    chassis_code = Column(String(64), comment="底盘代码")
    note = Column(String(512), comment="备注")


class Stock(Base):
    """库存表（ETL 自金蝶 FAVAILABLEQTY，ADR-17）"""
    __tablename__ = "stock"

    sku_code = Column(String(64), ForeignKey("product.sku_code"), primary_key=True, comment="SKU 编码")
    on_hand = Column(Integer, default=0, comment="可用量 FAVAILABLEQTY")


class PurchaseOrder(Base):
    """在途 PO 表（ETL 自 PIM PO，ADR-17）"""
    __tablename__ = "purchase_order"
    __table_args__ = (
        Index("idx_po_sku_arrival", "sku_code", "plan_arrival_date"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    supplier_id = Column(String(64), comment="供应商 ID")
    plan_arrival_date = Column(String(16), comment="计划到货日期 FPLANARRIVALDATE")
    not_receive_qty = Column(Integer, default=0, comment="未收数量 FNOTRECEIVEQTY")


class SupplierMaterial(Base):
    """供应商维度交期表（ETL 自金蝶 BD_MATERIALSUPPLIER，ADR-27）"""
    __tablename__ = "supplier_material"
    __table_args__ = (
        Index("idx_sm_sku_default", "sku_code", "is_default"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    supplier_id = Column(String(64), nullable=False, comment="供应商 ID")
    is_default = Column(Boolean, default=False, comment="是否默认供应商 FISDEFAULTSUPPLIER")
    lead_time_supp = Column(Integer, comment="供应商交期 FLEADTIMESUPP（天）")


class SupplierMonthMax(Base):
    """历史月最大供货量表（ETL 自金蝶视图 V_MATERIAL_SUPPLIER_MONTH_MAX_QTY，ADR-36）"""
    __tablename__ = "supplier_month_max"
    __table_args__ = (
        Index("idx_smm_sku_supplier", "sku_code", "supplier_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    supplier_id = Column(String(64), nullable=False, comment="供应商 ID")
    max_month_qty = Column(Integer, comment="近 12 月月度最大入库数量")


class Price(Base):
    """分级价表（ETL 自金蝶 SAL_PRICEBASE，ADR-26）"""
    __tablename__ = "price"
    __table_args__ = (
        Index("idx_price_sku_customer", "sku_code", "customer_id"),
        Index("idx_price_sku_tier", "sku_code", "customer_tier"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku_code = Column(String(64), ForeignKey("product.sku_code"), nullable=False, comment="SKU 编码")
    customer_id = Column(String(64), comment="客户内码 FCUSTID（空=等级价）")
    customer_tier = Column(String(8), comment="客户等级编码 A/B/C/D")
    price = Column(Float, nullable=False, comment="单价")
    qty_low = Column(Integer, comment="数量区间下限 FQTYLOW")
    qty_high = Column(Integer, comment="数量区间上限 FQTYHIGH")
    is_include_tax = Column(Boolean, default=True, comment="是否含税 FISINCLUDETAX")
    tax_rate = Column(Float, comment="税率 FTAXRATE")
    currency = Column(String(8), default="CNY", comment="币种 FCURRENCYID")


class AuditLog(Base):
    """审计日志表（ADR-32）"""
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(String(64), nullable=False, comment="请求 ID")
    user_id = Column(String(64), nullable=False, comment="用户 ID")
    role = Column(String(32), nullable=False, comment="角色")
    intent = Column(String(32), comment="意图")
    query = Column(String(1024), comment="查询原文")
    hit_count = Column(Integer, default=0, comment="命中数")
    is_fallback = Column(Boolean, default=False, comment="是否兜底")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, comment="创建时间")
