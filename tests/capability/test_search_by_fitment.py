# plan-P3-4
"""search_by_fitment 工具测试：brand 映射/区间命中/未命中/兜底"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.capability.fitment_search import search_by_fitment


def _make_fitment(sku_code, brand, series, model, year_start=None, year_end=None, engine_code=None):
    row = MagicMock()
    row.sku_code = sku_code
    row.brand = brand
    row.series = series
    row.model = model
    row.year_start = year_start
    row.year_end = year_end
    row.engine_code = engine_code
    return row


def _make_product(sku_code, name="", image_url=""):
    row = MagicMock()
    row.sku_code = sku_code
    row.name = name
    row.image_url = image_url
    return row


def _make_oe_mapping(sku_code, oe_normalized, oe_raw, oe_type="原厂"):
    row = MagicMock()
    row.sku_code = sku_code
    row.oe_normalized = oe_normalized
    row.oe_raw = oe_raw
    row.oe_type = oe_type
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
def mock_settings():
    with patch("qipei_agent.capability.fitment_search.get_settings") as mock_gs:
        mock_settings_obj = MagicMock()
        mock_settings_obj.brand_normalize_config = {
            "大众": "VW",
            "Volkswagen": "VW",
            "宝马": "BMW",
            "": "UNKNOWN",
        }
        mock_gs.return_value = mock_settings_obj
        yield mock_settings_obj


class TestFitmentSearch:
    def test_exact_match(self, mock_db_session, mock_settings):
        """精确匹配车型"""
        mock_db_session.execute.side_effect = [
            MockDBResult([_make_fitment("SKU001", "VW", "Golf", "MK7", 2013, 2020)]),
            MockDBResult([_make_product("SKU001", "刹车片", "http://img/1.jpg")]),
            MockDBResult([_make_oe_mapping("SKU001", "6Q0820803C", "6Q0820803C")]),
        ]
        result = search_by_fitment("大众", "Golf", "MK7", year=2015, db_session=mock_db_session)
        assert len(result["skus"]) == 1
        sku = result["skus"][0]
        assert sku["sku_code"] == "SKU001"
        assert sku["name"] == "刹车片"
        assert len(sku["oe_list"]) == 1

    def test_brand_mapping(self, mock_db_session, mock_settings):
        """brand 经映射后匹配"""
        mock_db_session.execute.side_effect = [
            MockDBResult([_make_fitment("SKU001", "VW", "Golf", "MK7", 2013, 2020)]),
            MockDBResult([_make_product("SKU001", "刹车片")]),
            MockDBResult([]),
        ]
        result = search_by_fitment("Volkswagen", "Golf", "MK7", db_session=mock_db_session)
        assert len(result["skus"]) == 1

    def test_year_range_hit(self, mock_db_session, mock_settings):
        """year 落区间命中"""
        mock_db_session.execute.side_effect = [
            MockDBResult([_make_fitment("SKU001", "VW", "Golf", "MK7", 2013, 2020)]),
            MockDBResult([_make_product("SKU001", "刹车片")]),
            MockDBResult([]),
        ]
        result = search_by_fitment("大众", "Golf", "MK7", year=2018, db_session=mock_db_session)
        assert len(result["skus"]) == 1

    def test_year_range_miss(self, mock_db_session, mock_settings):
        """year 超出区间未命中"""
        mock_db_session.execute.side_effect = [
            MockDBResult([]),
        ]
        result = search_by_fitment("大众", "Golf", "MK7", year=2025, db_session=mock_db_session)
        assert result["skus"] == []

    def test_no_match(self, mock_db_session, mock_settings):
        """未命中返回空"""
        mock_db_session.execute.side_effect = [MockDBResult([])]
        result = search_by_fitment("大众", "Golf", "MK8", db_session=mock_db_session)
        assert result["skus"] == []

    def test_engine_code_filter(self, mock_db_session, mock_settings):
        """engine_code 可选过滤"""
        mock_db_session.execute.side_effect = [
            MockDBResult([_make_fitment("SKU001", "VW", "Golf", "MK7", 2013, 2020, engine_code="EA211")]),
            MockDBResult([_make_product("SKU001", "刹车片")]),
            MockDBResult([]),
        ]
        result = search_by_fitment("大众", "Golf", "MK7", engine_code="EA211", db_session=mock_db_session)
        assert len(result["skus"]) == 1


class TestFitmentNoFallback:
    """车型检索无兜底（ADR-28：兜底仅 OE 检索）"""

    def test_miss_returns_empty_no_fallback(self, mock_db_session, mock_settings):
        """未命中直接返回空，不触发兜底"""
        mock_db_session.execute.side_effect = [MockDBResult([])]
        result = search_by_fitment("大众", "Golf", "MK8", db_session=mock_db_session)
        assert result["skus"] == []
        # 确认只执行了一次查询（无兜底调用）
        assert mock_db_session.execute.call_count == 1

    def test_multiple_skus(self, mock_db_session, mock_settings):
        """多 SKU 返回"""
        fitments = [
            _make_fitment("SKU001", "VW", "Golf", "MK7", 2013, 2020),
            _make_fitment("SKU002", "VW", "Golf", "MK7", 2013, 2020),
        ]
        products = [
            _make_product("SKU001", "刹车片 A"),
            _make_product("SKU002", "刹车片 B"),
        ]
        mock_db_session.execute.side_effect = [
            MockDBResult(fitments),
            MockDBResult(products),
            MockDBResult([]),
        ]
        result = search_by_fitment("大众", "Golf", "MK7", db_session=mock_db_session)
        assert len(result["skus"]) == 2
