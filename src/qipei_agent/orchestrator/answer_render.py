# plan-P4-5
"""回答渲染（固定模板，不调 LLM）（ADR-13/33/31）"""


def render_answer(intent: str, params: dict, tool_results: dict) -> dict:
    """按固定模板渲染回答（ADR-33）

    Args:
        intent: 意图标识
        params: 抽取的参数
        tool_results: 聚合工具结果

    Returns:
        answer 字典 {text, skus, hit_count, is_fallback}
    """
    skus = _extract_skus(tool_results)
    hit_count = len(skus) if skus else 0

    if hit_count == 0:
        return {
            "text": "未找到匹配，已尝试兜底；建议宽松匹配或换车型查询。",
            "skus": [],
            "hit_count": 0,
            "is_fallback": True,
        }

    # 多 SKU 直接返回列表不追问（ADR-31）
    lines = [f"共 {hit_count} 个匹配 SKU："]
    for i, sku in enumerate(skus, 1):
        lines.append(_render_sku(i, sku))

    return {
        "text": "\n".join(lines),
        "skus": skus,
        "hit_count": hit_count,
        "is_fallback": False,
    }


def _extract_skus(tool_results: dict) -> list:
    """从工具结果中提取 SKU 列表"""
    # 优先从 search_by_oe 提取
    oe_result = tool_results.get("search_by_oe")
    if oe_result and oe_result.get("skus"):
        return oe_result["skus"]

    # 其次从 search_by_fitment 提取
    fitment_result = tool_results.get("search_by_fitment")
    if fitment_result and fitment_result.get("skus"):
        return fitment_result["skus"]

    return []


def _render_sku(index: int, sku: dict) -> str:
    """渲染单个 SKU 行"""
    sku_code = sku.get("sku_code", "")
    name = sku.get("name", "")
    label = sku.get("label", sku.get("oe_type", ""))

    # 适配车型
    fitments = sku.get("fitments", [])
    fitment_str = ""
    if fitments:
        f = fitments[0]
        brand = f.get("brand", "")
        series = f.get("series", "")
        model = f.get("model", "")
        y_start = f.get("year_start", "")
        y_end = f.get("year_end", "")
        fitment_str = f"适配：{brand} {series} {model}（{y_start}-{y_end}）"

    # 图片
    image_url = sku.get("image_url", "")
    image_str = f"图片：{image_url}" if image_url else ""

    # 库存/价格/交期（从工具结果中获取，此处简化）
    stock_str = ""
    price_str = ""
    lead_str = ""
    risk_str = ""

    parts = [f"{index}. {sku_code} {name} [{label}]"]
    if fitment_str:
        parts.append(f"   {fitment_str}")
    if image_str:
        parts.append(f"   {image_str}")
    if stock_str:
        parts.append(f"   {stock_str}")
    if price_str:
        parts.append(f"   {price_str}")
    if lead_str:
        parts.append(f"   {lead_str}")
    if risk_str:
        parts.append(f"   ⚠ {risk_str}")

    return "\n".join(parts)
