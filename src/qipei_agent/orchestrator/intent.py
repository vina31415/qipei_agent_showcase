# plan-P1-1,P4-2
"""意图识别（4 意图）：规则优先 + 豆包兜底（ADR-33/31）"""

import re

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.errors import E_LLM_FAILED, get_logger

logger = get_logger("intent")

# 4 意图（ADR-33）
INTENT_OE = "oe_query"
INTENT_FITMENT = "fitment_query"
INTENT_LEAD_TIME = "lead_time_query"
INTENT_COMPOSITE = "composite_query"

# 规则：OE 号正则（ADR-33: [A-Z0-9][A-Z0-9\s\-\.\/]{3,}）
OE_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9\s\-\.\/]{3,}")

# 品牌词典（从 config 加载）
BRAND_KEYS = frozenset({
    "VW", "AUDI", "BMW", "MERCEDES", "TOYOTA", "HONDA", "NISSAN",
    "FORD", "CHEVROLET", "HYUNDAI", "KIA", "MAZDA", "SUBARU",
    "SUZUKI", "MITSUBISHI", "ISUZU", "DAIHATSU", "PEUGEOT",
    "RENAULT", "CITROEN", "FIAT", "OPEL", "VOLVO", "SKODA",
    "SEAT", "PORSCHE", "LAND_ROVER", "JAGUAR", "MINI",
    "大众", "奥迪", "宝马", "奔驰", "丰田", "本田", "日产",
    "福特", "雪佛兰", "现代", "起亚", "马自达", "斯巴鲁",
    "铃木", "三菱", "五十铃", "大发", "标致", "雷诺",
    "雪铁龙", "菲亚特", "欧宝", "沃尔沃", "斯柯达",
    "西雅特", "保时捷", "路虎", "捷豹", "迷你",
})

# 关键词词典
OE_KEYWORDS = frozenset({"oe", "OE", "零件号", "零件", "配件号"})
FITMENT_KEYWORDS = frozenset({"适配", "车型", "车系", "品牌", "适用", "匹配"})
LEAD_TIME_KEYWORDS = frozenset({"交期", "到货", "发货", "多久", "几天", "lead time"})


def _has_oe_pattern(message: str) -> bool:
    """检测是否包含 OE 号模式"""
    return bool(OE_PATTERN.search(message.upper()))


def _has_brand(message: str) -> bool:
    """检测是否包含品牌词"""
    upper_msg = message.upper()
    return any(brand in upper_msg for brand in BRAND_KEYS)


def _has_fitment_context(message: str) -> bool:
    """检测是否包含车型上下文"""
    return any(kw in message for kw in FITMENT_KEYWORDS)


def _has_lead_time_context(message: str) -> bool:
    """检测是否包含交期上下文"""
    return any(kw in message for kw in LEAD_TIME_KEYWORDS)


def _has_oe_keyword(message: str) -> bool:
    """检测是否包含 OE 关键词"""
    return any(kw in message for kw in OE_KEYWORDS)


def classify_intent(message: str) -> tuple[str, dict]:
    """规则优先意图识别（ADR-33）

    Args:
        message: 用户查询消息

    Returns:
        (intent, params) 意图和抽取的参数
    """
    has_oe = _has_oe_pattern(message) or _has_oe_keyword(message)
    has_fitment = _has_fitment_context(message) or _has_brand(message)
    has_lead_time = _has_lead_time_context(message)

    # 规则判定
    if has_oe and (has_fitment or has_lead_time):
        # 同时有 OE 和车型/交期 → composite_query
        return INTENT_COMPOSITE, {"has_oe": has_oe, "has_fitment": has_fitment}
    elif has_oe:
        return INTENT_OE, {"has_oe": True}
    elif has_fitment:
        return INTENT_FITMENT, {"has_fitment": True}
    elif has_lead_time:
        return INTENT_LEAD_TIME, {"has_lead_time": True}

    # 规则 miss → 降级豆包 LLM（ADR-31/33）
    return _llm_fallback(message)


def _llm_fallback(message: str) -> tuple[str, dict]:
    """豆包 function calling 兜底（llm_timeout 2s，超时降级）"""
    try:
        get_settings()  # 验证配置可用
        # TODO: 实际调用豆包 API（function calling）
        # 当前占位：返回 composite_query 作为默认意图
        logger.warning(f"LLM fallback triggered for: {message}")
        return INTENT_COMPOSITE, {"fallback": True}
    except Exception as e:
        logger.error(f"LLM fallback failed: {e}")
        return INTENT_COMPOSITE, {"fallback": True, "error": E_LLM_FAILED}
