# plan-P1-1,P3-1,P3-2
"""能力层 FastAPI 应用：统一端点 + X-Request-Id 中间件 + 统一信封 + 请求校验"""

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field

from qipei_agent.capability.envelope import error_envelope, success_envelope
from qipei_agent.capability.normalize_oe import handle_normalize_oe
from qipei_agent.shared.errors import E_NOT_FOUND, get_logger
from qipei_agent.shared.request_id import generate_request_id

logger = get_logger("capability")

app = FastAPI(title="Qipei Capability Service")

# 6 工具白名单（spec §3.5）
VALID_TOOLS = frozenset({
    "normalize_oe",
    "search_by_oe",
    "search_by_fitment",
    "get_stock",
    "get_price",
    "calc_lead_time",
})

# 工具 handler 路由表（逐步填充）
TOOL_HANDLERS = {
    "normalize_oe": handle_normalize_oe,
}


class ToolRequest(BaseModel):
    """能力层请求体（ADR-34：必含 user_id + role）"""
    user_id: str = Field(..., description="用户 ID")
    role: str = Field(..., description="用户角色")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """X-Request-Id 中间件：读取或生成，注入到响应头与日志"""
    request_id = request.headers.get("X-Request-Id") or generate_request_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.post("/api/v1/tools/{tool}")
async def handle_tool(tool: str, request: Request, body: ToolRequest):
    """统一工具端点"""
    request_id: str = request.state.request_id

    if tool not in VALID_TOOLS:
        logger.warning(f"Unknown tool requested: {tool}")
        return error_envelope(request_id, E_NOT_FOUND, f"Tool '{tool}' not found")

    # 分发到具体工具 handler
    handler = TOOL_HANDLERS.get(tool)
    if handler:
        # 工具 handler 接收 body.model_dump() 中的业务参数（排除 user_id/role）
        payload = body.model_dump()
        payload.pop("user_id", None)
        payload.pop("role", None)
        result = handler(**payload)
        return success_envelope(request_id, result)

    # 未实现的工具返回占位
    return success_envelope(request_id, {"tool": tool, "status": "placeholder"})

