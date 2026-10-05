# plan-P5-9
"""规则命中率测试（ADR-38/31/24）：验证规则命中率≥95%"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from qipei_agent.orchestrator.intent import classify_intent

TEST_DIR = Path(__file__).parent
CORPUS_PATH = TEST_DIR / "intent_corpus.yaml"


def load_corpus():
    with open(CORPUS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_params_match(actual_params: dict, expected_params: dict) -> bool:
    """检查参数是否匹配（expected_params 中的键值都在 actual_params 中）"""
    for key, expected_value in expected_params.items():
        actual_value = actual_params.get(key)
        if actual_value != expected_value:
            return False
    return True


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock get_settings 避免环境变量缺失导致 LLM fallback 失败"""
    mock = MagicMock()
    with patch("qipei_agent.orchestrator.intent.get_settings", return_value=mock):
        yield mock


def test_corpus_size(corpus):
    """验证 corpus 条数≥200"""
    assert len(corpus) >= 200, f"Corpus has {len(corpus)} items, need ≥200"


def test_corpus_coverage(corpus):
    """验证 corpus 覆盖四类意图"""
    intents = {item["expected_intent"] for item in corpus}
    assert "oe_query" in intents, "Missing oe_query samples"
    assert "fitment_query" in intents, "Missing fitment_query samples"
    assert "lead_time_query" in intents, "Missing lead_time_query samples"
    assert "composite_query" in intents, "Missing composite_query samples"


def test_rule_hit_rate(corpus):
    """规则命中率≥95%（意图正确且参数完全正确=命中）"""
    hits = 0
    misses = []

    for item in corpus:
        query = item["query"]
        expected_intent = item["expected_intent"]
        expected_params = item["expected_params"]

        actual_intent, actual_params = classify_intent(query)

        # 意图正确
        intent_ok = actual_intent == expected_intent

        # 参数匹配
        params_ok = check_params_match(actual_params, expected_params)

        if intent_ok and params_ok:
            hits += 1
        else:
            misses.append({
                "query": query,
                "expected": (expected_intent, expected_params),
                "actual": (actual_intent, actual_params),
            })

    total = len(corpus)
    hit_rate = hits / total * 100

    print(f"\nHit rate: {hit_rate:.1f}% ({hits}/{total})")
    if misses:
        print("\nMisses:")
        for m in misses[:10]:  # 只显示前 10 个
            print(f"  Q: {m['query']}")
            print(f"    Expected: {m['expected']}")
            print(f"    Actual:   {m['actual']}")

    assert hit_rate >= 95.0, f"Rule hit rate {hit_rate:.1f}% < 95%"
