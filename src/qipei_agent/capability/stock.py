# plan-P1-1,P3-5
"""get_stock 工具 handler：库存查询（ADR-17/34）"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from qipei_agent.shared.db import Stock
from qipei_agent.shared.errors import E_NOT_FOUND, get_logger

logger = get_logger("stock")


def get_stock(
    sku_code: str,
    db_session: Optional[Session] = None,
) -> dict:
    """库存查询

    输入：sku_code
    输出：{sku_code, on_hand}
    """
    if db_session is None:
        raise ValueError("db_session is required")

    stmt = select(Stock).where(Stock.sku_code == sku_code)
    row = db_session.execute(stmt).scalar_one_or_none()

    if row is None:
        raise ValueError(E_NOT_FOUND)

    return {"sku_code": row.sku_code, "on_hand": row.on_hand}
