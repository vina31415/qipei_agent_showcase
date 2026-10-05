# plan-P1-1,P2-4
"""OE 归一化流水线（ADR-15 v2 定稿）"""

import re
from typing import Optional

from qipei_agent.shared.config import get_settings


class OENormalizer:
    """OE 归一化器（规则从 config/oe_normalize.yaml 加载）"""

    def __init__(self):
        config = get_settings().oe_normalize_config
        self._prefixes = config.get("prefixes", [])
        # 按长度降序排列
        self._prefixes.sort(key=len, reverse=True)
        self._separators = config.get("separators", [])
        self._strip_leading_zeros = config.get("strip_leading_zeros", True)
        self._invalid_on_empty = config.get("invalid_on_empty", True)
        # 构建前缀匹配正则
        self._prefix_pattern = self._build_prefix_pattern()

    def _build_prefix_pattern(self) -> re.Pattern:
        """构建前缀匹配正则（长度降序，含标点边界处理）"""
        parts = []
        for prefix in self._prefixes:
            # 含标点前缀自带边界，无标点后缀的前缀需加边界
            has_punctuation = any(c in prefix for c in ".#°")
            if has_punctuation:
                parts.append(re.escape(prefix))
            else:
                # 无标点后缀：匹配后必须紧跟非字母数字或字符串结尾
                parts.append(re.escape(prefix) + r"(?=[^A-Za-z0-9]|$)")
        return re.compile("|".join(parts), re.IGNORECASE)

    def normalize(self, oe_raw: str) -> Optional[str]:
        """归一化单个 OE 号

        流水线：
        1. trim 首尾空白
        2. 统一大写
        3. 去前缀（按长度降序）
        4. 去所有非字母数字字符
        5. 纯数字 OE 去前导零
        6. 空串 → 无效 OE
        """
        if not oe_raw or not oe_raw.strip():
            return None

        # 1. trim
        result = oe_raw.strip()
        # 2. 大写
        result = result.upper()
        # 3. 去前缀
        result = self._prefix_pattern.sub("", result, count=1)
        # 4. 去非字母数字
        result = re.sub(r"[^A-Z0-9]", "", result)

        if not result:
            return None

        # 5. 纯数字去前导零
        if result.isdigit() and self._strip_leading_zeros:
            result = result.lstrip("0")

        # 6. 空串 → 无效
        if not result and self._invalid_on_empty:
            return None

        return result

    def get_oe_base(self, oe_normalized: str) -> Optional[str]:
        """获取基号（去末尾连续字母，宽松匹配用）"""
        if not oe_normalized:
            return None
        base = re.sub(r"[A-Z]+$", "", oe_normalized)
        return base if base else None

    def is_valid(self, oe_raw: str) -> bool:
        """判断 OE 号是否有效（非空且归一化后非空）"""
        return self.normalize(oe_raw) is not None
