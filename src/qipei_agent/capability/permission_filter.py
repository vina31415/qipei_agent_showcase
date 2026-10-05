# plan-P1-1,P3-8
"""能力层权限过滤：按 ADR-07 矩阵过滤工具响应字段"""

from qipei_agent.shared.permissions import filter_fields, filter_sku_list


def apply_permission_filter(role: str, response: dict) -> dict:
    """对能力层工具响应应用权限过滤

    Args:
        role: 角色标识（sales / merchandiser / cs / warehouse）
        response: 工具原始响应（含 skus 或其他 data）

    Returns:
        过滤后的响应
    """
    if "skus" in response:
        response["skus"] = filter_sku_list(role, response["skus"])
    elif "data" in response:
        response["data"] = filter_fields(role, response["data"])
    return response
