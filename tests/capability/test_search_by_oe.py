# plan-P3-3
"""search_by_oe 工具测试：命中/未命中/兜底/多 SKU 排序/宽松模式标注"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.capability.oe_search import search_by_oe


def _make_oe_mapping(sku_code, oe_normalized, oe_raw, oe_type="原厂", oe_base=None):
    row = MagicMock()
    row.sku_code = sku_code
    row.oe_normalized = oe_normalized
    row.oe_raw = oe_raw
    row.oe_type = oe_type
    row.oe_base = oe_base
    return row


def _make_product(sku_code, name="", image_url=""):
    row = MagicMock()
    row.sku_code = sku_code
    row.name = name
    row.image_url = image_url
    return row


class MockDBResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        mock = MagicMock()
        mock.all.return_value = self._rows
        return mock


@pytest.fixture
def mock_db_session():
    return MagicMock()


@pytest.fixture
def mock_kingdee_client():
    client = MagicMock()
    client.query_oe_fallback = MagicMock()
    return client


class TestOESearchHit:
    def test_exact_match_single(self, mock_db_session):
        mock_db_session.execute.side_effect = [
            MockDBResult([_make_oe_mapping("SKU001", "986479012", "0986479012")]),
            MockDBResult([_make_product("SKU001", "刹车片", "http://img/1.jpg")]),
        ]
        result = search_by_oe("986479012", db_session=mock_db_session)
        assert len(result["skus"]) == 1
        sku = result["skus"][0]
        assert sku["sku_code"] == "SKU001"
        assert sku["name"] == "刹车片"
        assert sku["label"] == ""

    def test_exact_match_multiple_sorting(self, mock_db_session):
        mappings = [
            _make_oe_mapping("SKU003", "986479012", "0986479012", "REF"),
            _make_oe_mapping("SKU001", "986479012", "0986479012", "原厂"),
            _make_oe_mapping("SKU002", "986479012", "0986479012", "原厂"),
        ]
        products = [
            _make_product("SKU001", "A"),
            _make_product("SKU002", "B"),
            _make_product("SKU003", "C"),
        ]
        mock_db_session.execute.side_effect = [
            MockDBResult(mappings),
            MockDBResult(products),
        ]
        result = search_by_oe("986479012", db_session=mock_db_session)
        sku_codes = [s["sku_code"] for s in result["skus"]]
        assert sku_codes == ["SKU001", "SKU002", "SKU003"]


class TestLooseMatch:
    def test_loose_match_by_base(self, mock_db_session):
        mappings = [
            _make_oe_mapping("SKU001", "6Q0820803C", "6Q0820803C", oe_base="6Q0820803"),
        ]
        products = [_make_product("SKU001", "减震器")]
        mock_db_session.execute.side_effect = [
            MockDBResult(mappings),
            MockDBResult(products),
        ]
        result = search_by_oe("6Q0820803", loose=True, db_session=mock_db_session)
        assert len(result["skus"]) == 1
        assert result["skus"][0]["label"] == "【宽松匹配，已剔除末尾后缀字母，请业务员复核】"


class TestFallback:
    def test_fallback_on_miss(self, mock_db_session, mock_kingdee_client):
        mock_db_session.execute.return_value = MockDBResult([])
        mock_kingdee_client.query_oe_fallback.return_value = {
            "is_success": True,
            "rows": [{"FMATERIALID": "KINGDEE001", "FOENO": "986479012", "FOETYPE": "原厂"}],
            "total_count": 1,
        }
        with patch("qipei_agent.capability.oe_search.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = mock_kingdee_client.query_oe_fallback.return_value
            result = search_by_oe("986479012", db_session=mock_db_session, kingdee_client=mock_kingdee_client)
        assert len(result["skus"]) == 1
        assert result["skus"][0]["sku_code"] == "KINGDEE001"
        assert result["skus"][0]["label"] == "【金蝶兜底】"

    def test_no_fallback_without_client(self, mock_db_session):
        mock_db_session.execute.return_value = MockDBResult([])
        result = search_by_oe("986479012", db_session=mock_db_session)
        assert result["skus"] == []

    def test_fallback_empty_result(self, mock_db_session, mock_kingdee_client):
        mock_db_session.execute.return_value = MockDBResult([])
        mock_kingdee_client.query_oe_fallback.return_value = {"is_success": True, "rows": [], "total_count": 0}
        with patch("qipei_agent.capability.oe_search.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = mock_kingdee_client.query_oe_fallback.return_value
            result = search_by_oe("986479012", db_session=mock_db_session, kingdee_client=mock_kingdee_client)
        assert result["skus"] == []

    def test_fallback_only_kingdee_no_pim(self, mock_db_session, mock_kingdee_client):
        """兜底只调金蝶（无 PIM 实时）"""
        mock_db_session.execute.return_value = MockDBResult([])
        mock_kingdee_client.query_oe_fallback.return_value = {
            "is_success": True,
            "rows": [{"FMATERIALID": "KINGDEE002", "FOENO": "1K0615301AA", "FOETYPE": "原厂"}],
            "total_count": 1,
        }
        with patch("qipei_agent.capability.oe_search.asyncio") as mock_asyncio:
            mock_loop = MagicMock()
            mock_asyncio.get_event_loop.return_value = mock_loop
            mock_loop.run_until_complete.return_value = mock_kingdee_client.query_oe_fallback.return_value
            result = search_by_oe("1K0615301AA", db_session=mock_db_session, kingdee_client=mock_kingdee_client)
        # 确认调用了金蝶兜底
        mock_kingdee_client.query_oe_fallback.assert_called_once()
        assert len(result["skus"]) == 1
        assert result["skus"][0]["label"] == "【金蝶兜底】"


class TestNoMatch:
    def test_no_match_no_fallback(self, mock_db_session):
        mock_db_session.execute.return_value = MockDBResult([])
        result = search_by_oe("NONEXISTENT", db_session=mock_db_session)
        assert result["skus"] == []
