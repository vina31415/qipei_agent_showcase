# plan-P1-3
"""request_id 生成与透传工具"""

import uuid


def generate_request_id() -> str:
    """生成唯一 request_id（UUID4）"""
    return str(uuid.uuid4())


def get_request_id(headers: dict, header_name: str = "X-Request-Id") -> str:
    """从请求头获取 request_id，不存在则生成新的"""
    rid = headers.get(header_name)
    if rid:
        return rid
    return generate_request_id()
