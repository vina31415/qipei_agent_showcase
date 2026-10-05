# plan-P1-1,P2-4
"""车型适配归一化（ADR-21）"""

import re
from typing import Optional

from qipei_agent.shared.config import get_settings


class FitmentNormalizer:
    """车型适配归一化器"""

    def __init__(self):
        self._brand_map = get_settings().brand_normalize_config

    def normalize_brand(self, brand: str) -> str:
        """归一化 brand（映射到标准编码）"""
        if not brand:
            return self._brand_map.get("", "UNKNOWN")
        # 精确匹配
        if brand in self._brand_map:
            return self._brand_map[brand]
        # 忽略大小写匹配
        brand_lower = brand.lower()
        for key, value in self._brand_map.items():
            if key and key.lower() == brand_lower:
                return value
        return brand.upper() if brand else "UNKNOWN"

    def normalize_engine_code(self, engine_code: Optional[str]) -> Optional[str]:
        """归一化 engine_code（大写 + 去空格）"""
        if not engine_code:
            return None
        return engine_code.upper().replace(" ", "")

    def normalize_model(self, model: str) -> str:
        """归一化 model（忽略大小写、剔除前后空格、压缩中间多余空格）"""
        if not model:
            return ""
        result = model.strip()
        result = re.sub(r"\s+", " ", result)
        return result

    def normalize_record(self, record: dict) -> dict:
        """归一化单条车型记录"""
        return {
            "brand": self.normalize_brand(record.get("brand", "")),
            "series": record.get("series", "").strip(),
            "model": self.normalize_model(record.get("model", "")),
            "engine_code": self.normalize_engine_code(record.get("engineCode")),
            "year_start": record.get("yearStart"),
            "year_end": record.get("yearEnd"),
            "chassis_code": record.get("chassisCode", "").strip(),
            "note": record.get("note", "").strip(),
        }
