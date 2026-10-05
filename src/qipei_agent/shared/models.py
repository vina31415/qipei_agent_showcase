# plan-P1-3
"""Pydantic 模型：统一信封 + 6 工具响应 schema（ADR-34）"""

from typing import Any, Optional

from pydantic import BaseModel, Field

# ─── 统一信封（ADR-30 / ADR-34） ───

class ErrorDetail(BaseModel):
    code: str
    message: str


class Envelope(BaseModel):
    """统一响应信封"""
    request_id: str
    ok: bool
    data: Optional[Any] = None
    error: Optional[ErrorDetail] = None


# ─── normalize_oe ───

class NormalizeOeData(BaseModel):
    oe_normalized: str
    is_valid: bool


# ─── search_by_oe ───

class FitmentInfo(BaseModel):
    brand: str
    series: str
    model: str
    year_start: int
    year_end: int


class OeSkuItem(BaseModel):
    sku_code: str
    name: str
    oe_raw: str
    oe_type: str  # 原厂 / REF
    label: str   # 原厂OE / REF参考号
    image_url: Optional[str] = None
    fitments: list[FitmentInfo] = Field(default_factory=list)


class SearchByOeData(BaseModel):
    skus: list[OeSkuItem] = Field(default_factory=list)


# ─── search_by_fitment ───

class OeInfo(BaseModel):
    oe_raw: str
    oe_type: str
    label: str


class FitmentSkuItem(BaseModel):
    sku_code: str
    name: str
    oe_list: list[OeInfo] = Field(default_factory=list)
    image_url: Optional[str] = None


class SearchByFitmentData(BaseModel):
    skus: list[FitmentSkuItem] = Field(default_factory=list)


# ─── get_stock ───

class GetStockData(BaseModel):
    sku_code: str
    on_hand: int


# ─── get_price ───

class GetPriceData(BaseModel):
    sku_code: str
    price: float
    tax_included: bool
    original_price: Optional[float] = None
    currency: str
    customer_tier: str
    price_type: str  # 专属价 / 等级价 / 人工询价
    qty_range: list[int] = Field(default_factory=list)  # [qty_low, qty_high]
    note: str = ""


# ─── calc_lead_time ───

class LeadTimeSegment(BaseModel):
    segment: str  # 现货 / 在途 / 采购
    qty: int
    lead_time: int
    arrival_date: Optional[str] = None


class PoInfo(BaseModel):
    supplier: str
    arrival_date: str
    qty: int


class AlternativeSupplier(BaseModel):
    supplier: str
    lead_time: int


class CalcLeadTimeData(BaseModel):
    sku_code: str
    lead_time: int  # 主交期单一值 = max(各段 lead_time)
    split: list[LeadTimeSegment] = Field(default_factory=list)
    supplier_note: str = ""
    risk_level: str = "none"  # none / medium / high
    risk_hint: str = ""
    pos: list[PoInfo] = Field(default_factory=list)
    alternatives: list[AlternativeSupplier] = Field(default_factory=list)
