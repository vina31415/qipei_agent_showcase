# plan-P1-1,P3-1
"""统一信封：成功 {request_id, ok: true, data} / 失败 {request_id, ok: false, error{code, message}}"""

from qipei_agent.shared.errors import make_error


def success_envelope(request_id: str, data: dict) -> dict:
    """成功信封"""
    return {"request_id": request_id, "ok": True, "data": data}


def error_envelope(request_id: str, code: str, message: str) -> dict:
    """失败信封"""
    return {"request_id": request_id, "ok": False, "error": make_error(code, message)}
