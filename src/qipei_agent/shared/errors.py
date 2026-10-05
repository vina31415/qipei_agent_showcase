# plan-P1-3
"""统一错误码 + 结构化 JSON 日志（request_id 贯穿全链路）"""

import json
import logging

# 统一错误码（spec §3.5 / ADR-22）
E_KINGDEE_TIMEOUT = "E_KINGDEE_TIMEOUT"
E_PIM_UNAVAILABLE = "E_PIM_UNAVAILABLE"
E_NOT_FOUND = "E_NOT_FOUND"
E_LLM_FAILED = "E_LLM_FAILED"
E_RATE_LIMIT = "E_RATE_LIMIT"


class AppError:
    """结构化错误对象"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


def make_error(code: str, message: str) -> dict:
    """构造错误信封 error 字段"""
    return {"code": code, "message": message}


# 结构化 JSON 日志
class JsonFormatter(logging.Formatter):
    """JSON 格式日志，每条带 request_id"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "level": record.levelname,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # 附加 request_id（如果存在）
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id
        # 附加额外字段
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    """获取结构化 JSON logger"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
