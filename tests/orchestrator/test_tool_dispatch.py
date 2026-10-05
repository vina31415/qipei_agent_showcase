# plan-P4-4
"""工具调度测试：按意图顺序调用能力层工具"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.orchestrator.tool_dispatch import dispatch_tools


@pytest.fixture
def mock_httpx():
    with patch("qipei_agent.orchestrator.tool_dispatch.httpx.Client") as mock_client:
        yield mock_client


def test_dispatch_oe_query(mock_httpx):
    """OE 查询：normalize_oe → search_by_oe"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "data": {"oe_normalized": "1K0615301AA", "is_valid": True}}
    mock_resp.raise_for_status = MagicMock()
    mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

    result = dispatch_tools("oe_query", {"oe_codes": "1K0615301AA"}, "req-1")
    assert result["intent"] == "oe_query"
    assert "normalize_oe" in result["tool_results"]
    assert "search_by_oe" in result["tool_results"]


def test_dispatch_fitment_query(mock_httpx):
    """车型查询：search_by_fitment"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "data": {"skus": []}}
    mock_resp.raise_for_status = MagicMock()
    mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

    result = dispatch_tools("fitment_query", {"brand": "VW", "year": 2005}, "req-2")
    assert result["intent"] == "fitment_query"
    assert "search_by_fitment" in result["tool_results"]


def test_dispatch_lead_time_query(mock_httpx):
    """交期查询：calc_lead_time"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": True, "data": {"lead_time": 5}}
    mock_resp.raise_for_status = MagicMock()
    mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

    result = dispatch_tools("lead_time_query", {"sku_code": "SKU-001"}, "req-3")
    assert result["intent"] == "lead_time_query"
    assert "calc_lead_time" in result["tool_results"]


def test_dispatch_composite_query(mock_httpx):
    """组合查询：OE → SKU → 库存 → 价格 → 交期"""
    call_count = [0]

    def side_effect(*args, **kwargs):
        call_count[0] += 1
        resp = MagicMock()
        if call_count[0] == 1:
            resp.json.return_value = {"ok": True, "data": {"oe_normalized": "1K0615301AA", "is_valid": True}}
        elif call_count[0] == 2:
            resp.json.return_value = {"ok": True, "data": {"skus": [{"sku_code": "SKU-001"}]}}
        else:
            resp.json.return_value = {"ok": True, "data": {}}
        resp.raise_for_status = MagicMock()
        return resp

    mock_httpx.return_value.__enter__.return_value.post.side_effect = side_effect

    result = dispatch_tools("composite_query", {"oe_codes": "1K0615301AA", "qty": 100}, "req-4")
    assert result["intent"] == "composite_query"
    assert "normalize_oe" in result["tool_results"]
    assert "search_by_oe" in result["tool_results"]
    assert "get_stock" in result["tool_results"]
    assert "get_price" in result["tool_results"]
    assert "calc_lead_time" in result["tool_results"]


def test_dispatch_tool_error(mock_httpx):
    """工具调用失败时降级"""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": {"code": "E_NOT_FOUND", "message": "not found"}}
    mock_resp.raise_for_status = MagicMock()
    mock_httpx.return_value.__enter__.return_value.post.return_value = mock_resp

    result = dispatch_tools("oe_query", {"oe_codes": "INVALID"}, "req-5")
    assert result["tool_results"]["normalize_oe"] is None


def test_dispatch_tool_exception(mock_httpx):
    """工具调用异常时降级"""
    mock_httpx.return_value.__enter__.return_value.post.side_effect = Exception("Connection error")

    result = dispatch_tools("oe_query", {"oe_codes": "1K0615301AA"}, "req-6")
    assert result["tool_results"]["normalize_oe"] is None
