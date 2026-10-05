# plan-P1-1,P4-3
"""参数抽取（规则优先 + 豆包兜底）（ADR-33/15/21）"""

import re
from typing import Optional

import yaml

from qipei_agent.shared.config import CONFIG_DIR
from qipei_agent.shared.errors import get_logger

logger = get_logger("param_extract")

# OE 号正则（ADR-15/33）
OE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9\s\-\.\/]{3,}")

# 年份正则（ADR-33: 19\d{2}|20\d{2}）
YEAR_PATTERN = re.compile(r"(19\d{2}|20\d{2})")

# 数量正则（ADR-33: \d+\s*(件|套|只|个)）
QTY_PATTERN = re.compile(r"(\d+)\s*(?:件|套|只|个)")

# 加载品牌词典
_brand_map: Optional[dict] = None


def _load_brand_map() -> dict:
    global _brand_map
    if _brand_map is None:
        path = CONFIG_DIR / "brand_normalize.yaml"
        with open(path, encoding="utf-8") as f:
            _brand_map = yaml.safe_load(f) or {}
    return _brand_map


def normalize_brand(raw_brand: str) -> str:
    """品牌归一化（brand_normalize.yaml）"""
    brand_map = _load_brand_map()
    return brand_map.get(raw_brand, raw_brand.upper())


def extract_oe(message: str) -> Optional[str]:
    """提取 OE 号（去除前缀）"""
    upper_msg = message.upper()
    # 去除已知前缀
    for prefix in ["OEM#", "OE#", "REF.NO.", "OEM", "OE", "REF", "NO.", "N°"]:
        if upper_msg.startswith(prefix):
            upper_msg = upper_msg[len(prefix):].lstrip(" :.-")
            break
        idx = upper_msg.find(prefix + " ")
        if idx >= 0:
            upper_msg = upper_msg[idx + len(prefix) + 1:].lstrip(" :.-")
            break

    match = OE_PATTERN.search(upper_msg)
    if match:
        return match.group(0).strip()
    return None


def extract_year(message: str) -> Optional[int]:
    """提取年份"""
    match = YEAR_PATTERN.search(message)
    if match:
        return int(match.group(1))
    return None


def extract_qty(message: str) -> Optional[int]:
    """提取数量"""
    match = QTY_PATTERN.search(message)
    if match:
        return int(match.group(1))
    return None


def extract_brand(message: str) -> Optional[str]:
    """提取品牌（词典匹配）"""
    brand_map = _load_brand_map()
    upper_msg = message.upper()
    for raw, normalized in brand_map.items():
        if raw and raw.upper() in upper_msg:
            return normalized
    return None


def extract_params(message: str, intent: str) -> dict:
    """规则优先参数抽取（ADR-33）

    Args:
        message: 用户查询消息
        intent: 已识别的意图

    Returns:
        params 字典 {oe_codes, brand, series, model, year, qty}
    """
    params: dict = {
        "oe_codes": None,
        "brand": None,
        "series": None,
        "model": None,
        "year": None,
        "qty": None,
    }

    # OE 号抽取
    oe = extract_oe(message)
    if oe:
        params["oe_codes"] = oe

    # 品牌抽取
    brand = extract_brand(message)
    if brand:
        params["brand"] = brand

    # 年份抽取
    year = extract_year(message)
    if year:
        params["year"] = year

    # 数量抽取
    qty = extract_qty(message)
    if qty:
        params["qty"] = qty

    # 参数校验
    if params["qty"] is not None and params["qty"] <= 0:
        params["qty"] = None

    return params
