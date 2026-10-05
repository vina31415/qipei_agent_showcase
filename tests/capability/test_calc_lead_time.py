# plan-P3-7
"""calc_lead_time 工具测试：三分支/现货不足拆分/多PO升序+不足拆分/默认供应商优先+无默认取最短/risk 等级"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.capability.lead_time import calc_lead_time


def _make_product(sku_code, lead_time_override=None, procurement_cycle=None):
    row = MagicMock()
    row.sku_code = sku_code
    row.lead_time_override = lead_time_override
    row.procurement_cycle = procurement_cycle
    return row


def _make_stock(sku_code, on_hand=0):
    row = MagicMock()
    row.sku_code = sku_code
    row.on_hand = on_hand
    return row


def _make_po(sku_code, supplier_id="SUP1", plan_arrival_date=None, not_receive_qty=0):
    row = MagicMock()
    row.sku_code = sku_code
    row.supplier_id = supplier_id
    row.plan_arrival_date = plan_arrival_date
    row.not_receive_qty = not_receive_qty
    return row


def _make_supplier_material(sku_code, supplier_id, is_default=False, lead_time_supp=15):
    row = MagicMock()
    row.sku_code = sku_code
    row.supplier_id = supplier_id
    row.is_default = is_default
    row.lead_time_supp = lead_time_supp
    return row


def _make_supplier_month_max(sku_code, supplier_id, max_month_qty=100):
    row = MagicMock()
    row.sku_code = sku_code
    row.supplier_id = supplier_id
    row.max_month_qty = max_month_qty
    return row


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_settings():
    with patch("qipei_agent.capability.lead_time.get_settings") as mock_gs:
        mock_settings_obj = MagicMock()
        mock_settings_obj.app_config = {"spot_lead_time": 1, "procurement_cycle_default": 15}
        mock_gs.return_value = mock_settings_obj
        yield mock_settings_obj


class TestCalcLeadTime:
    def test_spot_only(self, mock_db_session, mock_settings):
        """全现货"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 100))),
        ]
        result = calc_lead_time("SKU001", 50, db_session=mock_db_session)
        assert result["lead_time"] == 1
        assert len(result["split"]) == 1
        assert result["split"][0]["segment"] == "现货"

    def test_spot_insufficient_with_po(self, mock_db_session, mock_settings):
        """现货不足 + 在途 PO"""
        future = (date.today() + timedelta(days=10)).isoformat()
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 30))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_po("SKU001", plan_arrival_date=future, not_receive_qty=50),
            ])))),
        ]
        result = calc_lead_time("SKU001", 80, db_session=mock_db_session)
        assert len(result["split"]) == 2
        assert result["split"][0]["segment"] == "现货"
        assert result["split"][1]["segment"] == "在途"

    def test_no_spot_with_procurement(self, mock_db_session, mock_settings):
        """无现货 + 采购"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 50, db_session=mock_db_session)
        assert result["lead_time"] == 10
        assert result["split"][0]["segment"] == "采购"

    def test_default_supplier_priority(self, mock_db_session, mock_settings):
        """默认供应商优先"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=False, lead_time_supp=5),
                _make_supplier_material("SKU001", "SUP2", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 50, db_session=mock_db_session)
        assert result["split"][0]["lead_time"] == 10

    def test_risk_exceed_month_max(self, mock_db_session, mock_settings):
        """risk: 超历史月最大供货"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_supplier_month_max("SKU001", "SUP1", 100))),
        ]
        result = calc_lead_time("SKU001", 200, db_session=mock_db_session)
        assert result["risk_level"] == "high"

    def test_no_history_risk(self, mock_db_session, mock_settings):
        """risk: 无历史供货数据"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 50, db_session=mock_db_session)
        assert result["risk_level"] == "medium"
        assert "无历史供货数据" in result["risk_hint"]

    def test_adr37_example(self, mock_db_session, mock_settings):
        """ADR-37 示例：需求600，现货100，在途300，缺口200"""
        future = (date.today() + timedelta(days=10)).isoformat()
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 100))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_po("SKU001", plan_arrival_date=future, not_receive_qty=300),
            ])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_supplier_month_max("SKU001", "SUP1", 500))),
        ]
        result = calc_lead_time("SKU001", 600, db_session=mock_db_session)
        assert len(result["split"]) == 3
        assert result["split"][0] == {"segment": "现货", "qty": 100, "lead_time": 1}
        assert result["split"][1]["segment"] == "在途"
        assert result["split"][1]["qty"] == 300
        assert result["split"][2] == {"segment": "采购", "qty": 200, "lead_time": 10}
        assert result["lead_time"] == max(1, result["split"][1]["lead_time"], 10)

    def test_multi_po_ascending(self, mock_db_session, mock_settings):
        """多 PO 升序取最早 + 不足拆分"""
        future1 = (date.today() + timedelta(days=5)).isoformat()
        future2 = (date.today() + timedelta(days=15)).isoformat()
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_po("SKU001", supplier_id="SUP1", plan_arrival_date=future1, not_receive_qty=100),
                _make_po("SKU001", supplier_id="SUP2", plan_arrival_date=future2, not_receive_qty=200),
            ])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=10),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 350, db_session=mock_db_session)
        # 现货0 + 在途100 + 在途200 + 采购50
        assert len(result["split"]) == 3
        assert result["split"][0]["segment"] == "在途"
        assert result["split"][0]["qty"] == 100
        assert result["split"][1]["segment"] == "在途"
        assert result["split"][1]["qty"] == 200
        assert result["split"][2]["segment"] == "采购"
        assert result["split"][2]["qty"] == 50

    def test_no_default_shortest_supplier(self, mock_db_session, mock_settings):
        """无默认供应商时取最短交期 + 标注"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 0))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=False, lead_time_supp=20),
                _make_supplier_material("SKU001", "SUP2", is_default=False, lead_time_supp=8),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 50, db_session=mock_db_session)
        assert result["split"][0]["lead_time"] == 8
        assert result["risk_level"] == "medium"
        assert "非默认供应商" in result["risk_hint"]

    def test_spot_insufficient_split_to_procurement(self, mock_db_session, mock_settings):
        """现货不足直接拆分到采购（无在途 PO）"""
        mock_db_session.execute.side_effect = [
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_product("SKU001"))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=_make_stock("SKU001", 30))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[
                _make_supplier_material("SKU001", "SUP1", is_default=True, lead_time_supp=12),
            ])))),
            MagicMock(scalar_one_or_none=MagicMock(return_value=None)),
        ]
        result = calc_lead_time("SKU001", 100, db_session=mock_db_session)
        assert len(result["split"]) == 2
        assert result["split"][0]["segment"] == "现货"
        assert result["split"][0]["qty"] == 30
        assert result["split"][1]["segment"] == "采购"
        assert result["split"][1]["qty"] == 70
