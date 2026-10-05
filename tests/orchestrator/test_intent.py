# plan-P4-2
"""意图识别测试：4 意图规则分类 + LLM 兜底"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.orchestrator.intent import (
    INTENT_COMPOSITE,
    INTENT_FITMENT,
    INTENT_LEAD_TIME,
    INTENT_OE,
    classify_intent,
)


@pytest.fixture(autouse=True)
def mock_settings():
    mock = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock):
        yield mock


# ─── OE 查询 ───

def test_oe_query_with_oe_number():
    intent, _ = classify_intent("查 OE 6Q0820803C")
    assert intent == INTENT_OE


def test_oe_query_with_prefix():
    intent, _ = classify_intent("OE:1K0615301AA")
    assert intent == INTENT_OE


def test_oe_query_with_keyword():
    intent, _ = classify_intent("零件号 986479012")
    assert intent == INTENT_OE


# ─── 车型查询 ───

def test_fitment_query_with_brand():
    intent, _ = classify_intent("大众高尔夫适配什么刹车片")
    assert intent == INTENT_FITMENT


def test_fitment_query_with_keyword():
    intent, _ = classify_intent("车型 大众 高尔夫")
    assert intent == INTENT_FITMENT


def test_fitment_query_with_chinese_brand():
    intent, _ = classify_intent("丰田卡罗拉配件")
    assert intent == INTENT_FITMENT


# ─── 交期查询 ───

def test_lead_time_query():
    intent, _ = classify_intent("这个配件交期多久")
    assert intent == INTENT_LEAD_TIME


def test_lead_time_query_keyword():
    intent, _ = classify_intent("这个配件多久能到货")
    assert intent == INTENT_LEAD_TIME


# ─── 组合查询 ───

def test_composite_query_oe_and_fitment():
    intent, _ = classify_intent("OE 6Q0820803C 适配大众高尔夫吗，库存多少")
    assert intent == INTENT_COMPOSITE


def test_composite_query_oe_and_lead_time():
    intent, _ = classify_intent("OE 1K0615301AA 交期几天")
    assert intent == INTENT_COMPOSITE


# ─── 默认/兜底 ───

def test_default_intent_on_miss():
    """规则 miss 时降级到 composite_query（LLM 兜底占位）"""
    intent, params = classify_intent("帮我查个配件")
    assert intent == INTENT_COMPOSITE
    assert params.get("fallback") is True


def test_llm_fallback_error():
    """LLM 兜底失败时仍返回 composite_query"""
    with patch("qipei_agent.orchestrator.intent.get_settings", side_effect=Exception("LLM error")):
        intent, params = classify_intent("无法识别的查询")
        assert intent == INTENT_COMPOSITE
        assert params.get("fallback") is True
