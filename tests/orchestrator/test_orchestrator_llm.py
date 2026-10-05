# plan-P5-8
"""编排层 LLM mock 测试：豆包超时/失败降级（ADR-31/33）"""

from unittest.mock import MagicMock, patch

from qipei_agent.orchestrator.intent import (
    INTENT_COMPOSITE,
    INTENT_FITMENT,
    INTENT_LEAD_TIME,
    INTENT_OE,
    _llm_fallback,
    classify_intent,
)
from qipei_agent.shared.errors import E_LLM_FAILED

# ─── 规则命中不调 LLM ───

def test_rule_hit_oe_no_llm():
    """OE 规则命中时不调用 LLM"""
    with patch("qipei_agent.orchestrator.intent._llm_fallback") as mock_llm:
        intent, _ = classify_intent("查 OE 6Q0820803C")
        mock_llm.assert_not_called()
        assert intent == INTENT_OE


def test_rule_hit_fitment_no_llm():
    """车型规则命中时不调用 LLM"""
    with patch("qipei_agent.orchestrator.intent._llm_fallback") as mock_llm:
        intent, _ = classify_intent("大众高尔夫适配什么")
        mock_llm.assert_not_called()
        assert intent == INTENT_FITMENT


def test_rule_hit_lead_time_no_llm():
    """交期规则命中时不调用 LLM"""
    with patch("qipei_agent.orchestrator.intent._llm_fallback") as mock_llm:
        intent, _ = classify_intent("这个配件交期多久")
        mock_llm.assert_not_called()
        assert intent == INTENT_LEAD_TIME


# ─── LLM 超时降级 ───

def test_llm_timeout_returns_composite():
    """豆包超时（>2s）→ 降级 composite_query"""
    with patch("qipei_agent.orchestrator.intent.get_settings", side_effect=TimeoutError("LLM timeout")):
        intent, params = _llm_fallback("帮我查个配件")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
        assert params.get("error") == E_LLM_FAILED


def test_llm_timeout_error_code():
    """超时降级携带 E_LLM_FAILED 错误码"""
    with patch("qipei_agent.orchestrator.intent.get_settings", side_effect=TimeoutError("timeout")):
        _, params = _llm_fallback("查询")
        assert "error" in params
        assert params["error"] == E_LLM_FAILED


# ─── LLM 失败降级 ───

def test_llm_api_error_returns_composite():
    """豆包 API 失败 → 降级 composite_query"""
    with patch("qipei_agent.orchestrator.intent.get_settings", side_effect=ConnectionError("API unreachable")):
        intent, params = _llm_fallback("帮我查个配件")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
        assert params.get("error") == E_LLM_FAILED


def test_llm_http_error_returns_composite():
    """豆包 HTTP 错误 → 降级 composite_query"""
    with patch("qipei_agent.orchestrator.intent.get_settings", side_effect=Exception("HTTP 500")):
        intent, params = _llm_fallback("帮我查个配件")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
        assert params.get("error") == E_LLM_FAILED


# ─── LLM 成功路径 ───

def test_llm_success_returns_composite():
    """LLM 成功时返回 composite_query + fallback=True"""
    mock_settings = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock_settings):
        intent, params = _llm_fallback("帮我查个配件")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
        assert "error" not in params


# ─── 规则 miss 触发 LLM ───

def test_rule_miss_triggers_llm():
    """规则 miss 时触发 LLM fallback"""
    mock_settings = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock_settings):
        intent, params = classify_intent("帮我查个配件")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True


def test_rule_miss_empty_message():
    """空消息触发 LLM fallback"""
    mock_settings = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock_settings):
        intent, params = classify_intent("")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True


def test_rule_miss_greeting():
    """问候语触发 LLM fallback"""
    mock_settings = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock_settings):
        intent, params = classify_intent("你好")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
