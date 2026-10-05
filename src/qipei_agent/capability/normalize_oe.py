# plan-P1-1,P3-2
"""normalize_oe 工具 handler（能力层，ADR-15 流水线）"""

from qipei_agent.etl.normalize_oe import OENormalizer

_normalizer: OENormalizer | None = None


def get_normalizer() -> OENormalizer:
    """懒加载单例"""
    global _normalizer
    if _normalizer is None:
        _normalizer = OENormalizer()
    return _normalizer


def handle_normalize_oe(oe_raw: str = "") -> dict:
    """OE 归一化工具入口

    输入：oe_raw（原始 OE 号字符串）
    输出：{oe_normalized, is_valid}
    """
    normalized = get_normalizer().normalize(oe_raw)
    return {
        "oe_normalized": normalized,
        "is_valid": normalized is not None,
    }
