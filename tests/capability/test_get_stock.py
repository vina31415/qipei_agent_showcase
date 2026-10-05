# plan-P3-5
"""get_stock 工具测试：命中/未命中→E_NOT_FOUND"""

from unittest.mock import MagicMock

import pytest

from qipei_agent.capability.stock import get_stock
from qipei_agent.shared.errors import E_NOT_FOUND


def _make_stock(sku_code, on_hand=0):
    row = MagicMock()
    row.sku_code = sku_code
    row.on_hand = on_hand
    return row


@pytest.fixture
def mock_db_session():
    return MagicMock()


class TestGetStock:
    def test_hit(self, mock_db_session):
        """命中返回库存"""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = _make_stock("SKU001", 100)
        result = get_stock("SKU001", db_session=mock_db_session)
        assert result["sku_code"] == "SKU001"
        assert result["on_hand"] == 100

    def test_miss_raises_not_found(self, mock_db_session):
        """未命中→E_NOT_FOUND"""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError, match=E_NOT_FOUND):
            get_stock("NONEXISTENT", db_session=mock_db_session)

    def test_zero_stock(self, mock_db_session):
        """库存为 0 仍返回"""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = _make_stock("SKU001", 0)
        result = get_stock("SKU001", db_session=mock_db_session)
        assert result["on_hand"] == 0

    def test_miss_no_fallback(self, mock_db_session):
        """未命中→E_NOT_FOUND，不兜底"""
        mock_db_session.execute.return_value.scalar_one_or_none.return_value = None
        with pytest.raises(ValueError, match=E_NOT_FOUND):
            get_stock("NONEXISTENT", db_session=mock_db_session)
