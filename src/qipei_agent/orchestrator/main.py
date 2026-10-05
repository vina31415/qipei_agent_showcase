# plan-P1-1,P4-1
"""编排层 FastAPI 应用：POST /api/v1/chat 入口、Redis 会话、审计写入（ADR-25/32/33）"""

from datetime import UTC, datetime
from typing import Optional

import redis
from fastapi import FastAPI, Request
from pydantic import BaseModel, Field
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.db import AuditLog
from qipei_agent.shared.errors import get_logger
from qipei_agent.shared.request_id import generate_request_id

logger = get_logger("orchestrator")

app = FastAPI(title="Qipei Orchestrator Service")

# ─── 依赖初始化（延迟，避免 import 时环境变量未设置） ───

_redis_client: Optional[redis.Redis] = None
_engine = None
_SessionLocal = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端（单例）"""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def get_db_session():
    """获取数据库 Session"""
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        db_url = f"mysql+pymysql://{settings.MYSQL_USER}:{settings.MYSQL_PASSWORD}@{settings.MYSQL_HOST}:{settings.MYSQL_PORT}/{settings.MYSQL_DB}"
        _engine = create_engine(db_url)
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal()


# ─── 请求/响应契约（ADR-25） ───

class ChatContext(BaseModel):
    """调用方上下文（信任调用方，不另做登录态校验）"""
    user_id: str = Field(..., description="用户 ID（ERP 侧账号/工号）")
    role: str = Field(..., description="用户角色：sales / merchandiser / warehouse / cs")
    customer_id: Optional[str] = Field(None, description="客户内码 FCUSTID")
    customer_tier: Optional[str] = Field(None, description="客户等级编码")
    currency: Optional[str] = Field(None, description="币种偏好，默认 CNY")
    quantity: Optional[int] = Field(None, description="询价数量（阶梯价）")


class ChatRequest(BaseModel):
    """POST /api/v1/chat 请求体"""
    session_id: Optional[str] = Field(None, description="会话 ID，首次不传由服务端生成")
    message: str = Field(..., description="用户查询消息")
    context: ChatContext = Field(..., description="调用方上下文")


class ChatResponse(BaseModel):
    """POST /api/v1/chat 响应体"""
    session_id: str
    request_id: str
    intent: Optional[str] = None
    answer: Optional[dict] = None


# ─── 会话管理（ADR-25 / ADR-33） ───

SESSION_PREFIX = "session:"
SESSION_TTL = 1800  # 30 分钟（秒），从 config/app.yaml 读取
HISTORY_MAX = 10    # 会话历史最多保留条数


def get_session(session_id: str) -> Optional[dict]:
    """从 Redis 获取会话状态"""
    r = get_redis()
    import json
    data = r.get(f"{SESSION_PREFIX}{session_id}")
    if data:
        return json.loads(data)
    return None


def save_session(session_id: str, session_data: dict) -> None:
    """保存会话状态到 Redis"""
    r = get_redis()
    import json
    # 限制历史长度
    history = session_data.get("history", [])
    if len(history) > HISTORY_MAX:
        session_data["history"] = history[-HISTORY_MAX:]
    r.setex(f"{SESSION_PREFIX}{session_id}", SESSION_TTL, json.dumps(session_data, ensure_ascii=False))


# ─── 审计写入（ADR-32） ───

def write_audit_log(
    request_id: str,
    user_id: str,
    role: str,
    intent: Optional[str],
    query: str,
    hit_count: int = 0,
    is_fallback: bool = False,
) -> None:
    """写入审计日志（脱敏：不记价格/库存数值）"""
    try:
        db = get_db_session()
        log_entry = AuditLog(
            request_id=request_id,
            user_id=user_id,
            role=role,
            intent=intent,
            query=query,
            hit_count=hit_count,
            is_fallback=is_fallback,
            created_at=datetime.now(UTC),
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"Audit log write failed: {e}")
    finally:
        try:
            db.close()
        except Exception:
            pass


# ─── 入口端点 ───

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """统一对话入口（ADR-25：信任调用方，不鉴权）"""
    # 生成/获取 request_id
    request_id = request.headers.get("X-Request-Id") or generate_request_id()

    # 生成/获取 session_id
    session_id = body.session_id or generate_request_id()

    # 获取会话上下文
    session_data = get_session(session_id) or {
        "intent": None,
        "params": {},
        "last_query": None,
        "history": [],
    }

    # 追加历史
    session_data["history"].append({
        "role": "user",
        "message": body.message,
    })
    session_data["last_query"] = body.message

    # TODO(P4-2~P4-5): 意图识别 → 参数抽取 → 工具调度 → 回答渲染
    # 当前占位：返回模板回答
    intent = session_data.get("intent")
    answer = {"text": f"收到查询：{body.message}（编排层工具链路待实现）"}

    # 更新会话
    session_data["history"].append({
        "role": "assistant",
        "answer": answer,
    })
    save_session(session_id, session_data)

    # 审计写入（ADR-32：脱敏，不记价格/库存）
    write_audit_log(
        request_id=request_id,
        user_id=body.context.user_id,
        role=body.context.role,
        intent=intent,
        query=body.message,
        hit_count=0,
        is_fallback=False,
    )

    logger.info("Chat request processed", extra={"request_id": request_id})

    return ChatResponse(
        session_id=session_id,
        request_id=request_id,
        intent=intent,
        answer=answer,
    )
