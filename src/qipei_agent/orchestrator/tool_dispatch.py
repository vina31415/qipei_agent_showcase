# plan-P1-1,P4-4
"""工具调度（ADR-33）：按意图顺序调用能力层工具"""

from typing import Optional

import httpx

from qipei_agent.shared.errors import get_logger

logger = get_logger("tool_dispatch")

# 能力层基础地址（内网）
# 实际部署时通过环境变量或配置注入
CAPABILITY_BASE_URL: Optional[str] = None


def _get_capability_url() -> str:
    global CAPABILITY_BASE_URL
    if CAPABILITY_BASE_URL is None:
        # 默认内网地址，实际由部署配置
        CAPABILITY_BASE_URL = "http://localhost:8001"
    return CAPABILITY_BASE_URL


def _call_tool(tool: str, payload: dict, request_id: str) -> Optional[dict]:
    """调用能力层工具"""
    url = f"{_get_capability_url()}/api/v1/tools/{tool}"
    headers = {"X-Request-Id": request_id}
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            if result.get("ok"):
                return result.get("data")
            else:
                error = result.get("error", {})
                logger.warning(f"Tool {tool} error: {error}")
                return None
    except Exception as e:
        logger.error(f"Tool {tool} call failed: {e}")
        return None


def dispatch_tools(intent: str, params: dict, request_id: str) -> dict:
    """按意图调度工具（ADR-33）

    Args:
        intent: 意图标识
        params: 抽取的参数
        request_id: 请求 ID

    Returns:
        聚合工具结果
    """
    result: dict = {"intent": intent, "params": params, "tool_results": {}}

    if intent == "oe_query":
        # normalize_oe → search_by_oe
        oe = params.get("oe_codes")
        if oe:
            norm = _call_tool("normalize_oe", {"oe_raw": oe}, request_id)
            result["tool_results"]["normalize_oe"] = norm
            if norm and norm.get("is_valid"):
                skus = _call_tool("search_by_oe", {"oe_normalized": norm["oe_normalized"]}, request_id)
                result["tool_results"]["search_by_oe"] = skus

    elif intent == "fitment_query":
        # search_by_fitment
        brand = params.get("brand")
        year = params.get("year")
        if brand:
            skus = _call_tool("search_by_fitment", {
                "brand": brand,
                "series": params.get("series", ""),
                "model": params.get("model", ""),
                "year": year,
            }, request_id)
            result["tool_results"]["search_by_fitment"] = skus

    elif intent == "lead_time_query":
        # calc_lead_time
        sku_code = params.get("sku_code")
        if sku_code:
            lead = _call_tool("calc_lead_time", {
                "sku_code": sku_code,
                "quantity": params.get("qty"),
            }, request_id)
            result["tool_results"]["calc_lead_time"] = lead

    elif intent == "composite_query":
        # OE → SKU → 库存 → 价格 → 交期
        oe = params.get("oe_codes")
        if oe:
            norm = _call_tool("normalize_oe", {"oe_raw": oe}, request_id)
            result["tool_results"]["normalize_oe"] = norm
            if norm and norm.get("is_valid"):
                skus = _call_tool("search_by_oe", {"oe_normalized": norm["oe_normalized"]}, request_id)
                result["tool_results"]["search_by_oe"] = skus
                if skus and skus.get("skus"):
                    sku_code = skus["skus"][0]["sku_code"]
                    # 并行调用库存/价格/交期
                    stock = _call_tool("get_stock", {"sku_code": sku_code}, request_id)
                    price = _call_tool("get_price", {
                        "sku_code": sku_code,
                        "customer_id": params.get("customer_id"),
                        "quantity": params.get("qty"),
                    }, request_id)
                    lead = _call_tool("calc_lead_time", {
                        "sku_code": sku_code,
                        "quantity": params.get("qty"),
                    }, request_id)
                    result["tool_results"]["get_stock"] = stock
                    result["tool_results"]["get_price"] = price
                    result["tool_results"]["calc_lead_time"] = lead

    return result
