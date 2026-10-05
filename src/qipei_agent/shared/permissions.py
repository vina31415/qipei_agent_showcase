# plan-P1-1,P1-3
"""权限过滤（ADR-07 矩阵）：按角色过滤返回字段"""


from qipei_agent.shared.config import get_settings


def filter_fields(role: str, data: dict) -> dict:
    """按 ADR-07 权限矩阵过滤字段

    Args:
        role: 角色标识（sales / merchandiser / cs / warehouse）
        data: 工具原始响应 data 字段

    Returns:
        过滤后的 data 字段（仅保留该角色可见的字段）
    """
    perm_config = get_settings().permission_config
    roles = perm_config.get("roles", {})
    role_cfg = roles.get(role)

    if role_cfg is None:
        # 未知角色：保守处理，返回空
        return {}

    visible_fields = role_cfg.get("visible_fields", [])
    hidden_fields = role_cfg.get("hidden_fields", [])

    # 如果有 visible_fields 白名单，只保留白名单中的字段
    if visible_fields:
        return {k: v for k, v in data.items() if k in visible_fields}

    # 否则用 hidden_fields 黑名单
    if hidden_fields:
        return {k: v for k, v in data.items() if k not in hidden_fields}

    # 无限制：返回全部
    return data


def filter_sku_list(role: str, skus: list[dict]) -> list[dict]:
    """过滤 SKU 列表中每个 SKU 的字段"""
    return [filter_fields(role, sku) for sku in skus]
