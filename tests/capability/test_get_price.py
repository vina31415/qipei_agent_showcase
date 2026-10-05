# plan-P3-6
"""get_price 工具测试：优先级/阶梯命中/超上限取最大/含税与未税/币种不换算"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.capability.price import get_price
from qipei_agent.shared.errors import E_NOT_FOUND


def _make_customer(customer_id, customer_tier="A"):
    row = MagicMock()
    row.customer_id = customer_id
    row.customer_tier = customer_tier
    return row


def _make_price(sku_code, customer_id=None, customer_tier=None, price=100.0,
                qty_low=0, qty_high=None, is_include_tax=True, tax_rate=13.0, currency="CNY"):
    row = MagicMock()
    row.sku_code = sku_code
    row.customer_id = customer_id
    row.customer_tier = customer_tier
    row.price = price
    row.qty_low = qty_low
    row.qty_high = qty_high
    row.is_include_tax = is_include_tax
    row.tax_rate = tax_rate
    row.currency = currency
    return row


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_settings():
    with patch("qipei_agent.capability.price.get_settings") as mock_gs:
        mock_settings_obj = MagicMock()
        mock_settings_obj.customer_level_config = {"A": "A", "B": "B", "C": "C", "D": "D"}
        mock_gs.return_value = mock_settings_obj
        yield mock_settings_obj


class TestGetPrice:
    def test_customer_specific_price(self, mock_db_session, mock_settings):
        """客户专属价优先"""
        price_row = _make_price("SKU001", customer_id="CUST1", price=90.0)
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[price_row])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["price"] == 90.0
        assert result["price_type"] == "专属价"

    def test_tier_price(self, mock_db_session, mock_settings):
        """等级价（无专属价时）"""
        price_row = _make_price("SKU001", customer_tier="B", price=100.0)
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "B"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[price_row])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["price"] == 100.0
        assert result["price_type"] == "等级价"

    def test_tier_quantity_range(self, mock_db_session, mock_settings):
        """阶梯区间命中"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", customer_tier="A", price=100.0, qty_low=0, qty_high=10),
                _make_price("SKU001", customer_tier="A", price=90.0, qty_low=11, qty_high=50),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 20, db_session=mock_db_session)
        assert result["price"] == 90.0

    def test_exceed_max_tier(self, mock_db_session, mock_settings):
        """超上限取最大阶梯"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", customer_tier="A", price=100.0, qty_low=0, qty_high=10),
                _make_price("SKU001", customer_tier="A", price=90.0, qty_low=11, qty_high=50),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 100, db_session=mock_db_session)
        assert result["price"] == 90.0

    def test_tax_included(self, mock_db_session, mock_settings):
        """含税价计算 original_price"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", customer_tier="A", price=113.0, is_include_tax=True, tax_rate=13.0),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["tax_included"] is True
        assert result["original_price"] == 100.0

    def test_not_found(self, mock_db_session, mock_settings):
        """无价格→E_NOT_FOUND"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
        ]
        with pytest.raises(ValueError, match=E_NOT_FOUND):
            get_price("SKU001", "CUST1", 10, db_session=mock_db_session)

    def test_currency_no_conversion(self, mock_db_session, mock_settings):
        """币种不换算"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", customer_tier="A", price=100.0, currency="USD"),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["currency"] == "USD"

    def test_inquiry_price_fallback(self, mock_db_session, mock_settings):
        """人工询价（无专属价+无等级价时）"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", price=80.0),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["price"] == 80.0
        assert result["price_type"] == "人工询价"

    def test_priority_chain(self, mock_db_session, mock_settings):
        """优先级链：专属价 > 等级价 > 人工询价"""
        specific = _make_price("SKU001", customer_id="CUST1", price=85.0)
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[specific])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["price"] == 85.0
        assert result["price_type"] == "专属价"

    def test_no_customer_tier_uses_inquiry(self, mock_db_session, mock_settings):
        """无 customer_tier 时直接走人工询价"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", None))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            # 等级价分支跳过（customer_tier 为 None）
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", price=75.0),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["price"] == 75.0
        assert result["price_type"] == "人工询价"

    def test_tax_excluded(self, mock_db_session, mock_settings):
        """未税价 original_price = price"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_customer("CUST1", "A"))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_price("SKU001", customer_tier="A", price=100.0, is_include_tax=False),
            ])))),
        ]
        result = get_price("SKU001", "CUST1", 10, db_session=mock_db_session)
        assert result["tax_included"] is False
        assert result["original_price"] == 100.0
