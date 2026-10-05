# plan-P4-5
"""回答渲染测试：固定模板拼接"""

from qipei_agent.orchestrator.answer_render import render_answer


def test_render_answer_with_skus():
    """有 SKU 匹配"""
    tool_results = {
        "search_by_oe": {
            "skus": [
                {
                    "sku_code": "SKU-001",
                    "name": "前刹车片",
                    "label": "原厂OE",
                    "fitments": [
                        {"brand": "VW", "series": "GOLF", "model": "GOLF IV", "year_start": 1997, "year_end": 2004}
                    ],
                }
            ]
        }
    }
    result = render_answer("oe_query", {}, tool_results)
    assert result["hit_count"] == 1
    assert result["is_fallback"] is False
    assert "SKU-001" in result["text"]
    assert "前刹车片" in result["text"]


def test_render_answer_no_skus():
    """无 SKU 匹配→兜底提示"""
    tool_results = {"search_by_oe": {"skus": []}}
    result = render_answer("oe_query", {}, tool_results)
    assert result["hit_count"] == 0
    assert result["is_fallback"] is True
    assert "未找到匹配" in result["text"]
    assert "建议宽松匹配" in result["text"]


def test_render_answer_multiple_skus():
    """多 SKU 直接返回列表不追问（ADR-31）"""
    tool_results = {
        "search_by_oe": {
            "skus": [
                {"sku_code": "SKU-001", "name": "刹车片 A", "label": "原厂OE", "fitments": []},
                {"sku_code": "SKU-002", "name": "刹车片 B", "label": "REF参考号", "fitments": []},
            ]
        }
    }
    result = render_answer("oe_query", {}, tool_results)
    assert result["hit_count"] == 2
    assert "SKU-001" in result["text"]
    assert "SKU-002" in result["text"]


def test_render_answer_fitment_query():
    """车型查询结果渲染"""
    tool_results = {
        "search_by_fitment": {
            "skus": [
                {"sku_code": "SKU-003", "name": "空气滤芯", "label": "原厂OE", "fitments": []}
            ]
        }
    }
    result = render_answer("fitment_query", {}, tool_results)
    assert result["hit_count"] == 1
    assert "SKU-003" in result["text"]


def test_render_answer_empty_tool_results():
    """空工具结果"""
    result = render_answer("oe_query", {}, {})
    assert result["hit_count"] == 0
    assert result["is_fallback"] is True
