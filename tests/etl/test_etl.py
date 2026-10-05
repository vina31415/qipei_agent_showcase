# plan-P2-4
"""ETL 归一化与装载测试"""

from unittest.mock import patch

import pytest

from qipei_agent.etl.normalize_fitment import FitmentNormalizer
from qipei_agent.etl.normalize_oe import OENormalizer


@pytest.fixture
def mock_settings():
    """Mock Settings with test config"""
    with patch("qipei_agent.etl.normalize_oe.get_settings") as mock_oe, \
         patch("qipei_agent.etl.normalize_fitment.get_settings") as mock_fit:
        mock_settings_obj = type(
            "MockSettings",
            (),
            {
                "oe_normalize_config": {
                    "prefixes": ["REF.NO.", "OEM#", "OEM", "OE#", "OE", "REF", "NO.", "N°"],
                    "separators": [" ", "-", "/", ".", "_", "#", ":", "°"],
                    "strip_leading_zeros": True,
                    "invalid_on_empty": True,
                },
                "brand_normalize_config": {
                    "大众": "VW", "Volkswagen": "VW", "vw": "VW",
                    "宝马": "BMW", "B.M.W": "BMW",
                    "奔驰": "MB", "Mercedes-Benz": "MB", "Mercedes": "MB",
                    "丰田": "TOYOTA", "Toyota": "TOYOTA",
                    "本田": "HONDA", "Honda": "HONDA",
                    "日产": "NISSAN", "Nissan": "NISSAN",
                    "奥迪": "AUDI", "Audi": "AUDI",
                    "博世": "BOSCH", "Bosch": "BOSCH",
                    "德尔福": "DELPHI", "Delphi": "DELPHI",
                    "大陆": "CONTINENTAL", "Continental": "CONTINENTAL",
                    "采埃孚": "ZF", "Z.F": "ZF",
                    "现代": "HYUNDAI", "起亚": "KIA", "马自达": "MAZDA",
                    "三菱": "MITSUBISHI", "福特": "FORD",
                    "菲亚特": "FIAT", "标致": "PEUGEOT", "雪铁龙": "CITROEN",
                    "": "UNKNOWN", None: "UNKNOWN",
                },
            },
        )()
        mock_oe.return_value = mock_settings_obj
        mock_fit.return_value = mock_settings_obj
        yield mock_settings_obj


class TestOENormalizer:
    """OE 归一化测试（ADR-15 v2）"""

    @pytest.fixture
    def normalizer(self, mock_settings):
        return OENormalizer()

    def test_trim_and_upper(self, normalizer):
        """trim 首尾空白 + 统一大写"""
        assert normalizer.normalize("  abc-123  ") == "ABC123"

    def test_remove_prefix_ref_no(self, normalizer):
        """去前缀 REF.NO."""
        assert normalizer.normalize("REF.NO.123456") == "123456"

    def test_remove_prefix_oem(self, normalizer):
        """去前缀 OEM（无标点，需边界匹配）"""
        assert normalizer.normalize("OEM-123456") == "123456"
        # OEM123456 不应去前缀（1 是字母数字，不满足边界条件）
        assert normalizer.normalize("OEM123456") == "OEM123456"

    def test_remove_prefix_oe(self, normalizer):
        """去前缀 OE（无标点，需边界匹配）"""
        # OE-0986479012 → 去 OE → 去分隔符 → 0986479012 → 纯数字去前导零 → 986479012
        assert normalizer.normalize("OE-0986479012") == "986479012"
        assert normalizer.normalize("OE#0986479012") == "986479012"

    def test_remove_prefix_ref(self, normalizer):
        """去前缀 REF"""
        assert normalizer.normalize("REF 123456") == "123456"

    def test_strip_leading_zeros_pure_numeric(self, normalizer):
        """纯数字 OE 去前导零"""
        assert normalizer.normalize("OE-0986479012") == "986479012"

    def test_no_strip_leading_zeros_with_letters(self, normalizer):
        """含字母 OE 不动前导零"""
        assert normalizer.normalize("0A123") == "0A123"

    def test_remove_separators(self, normalizer):
        """去分隔符"""
        assert normalizer.normalize("1K0-615-301") == "1K0615301"
        assert normalizer.normalize("1K0/615/301") == "1K0615301"
        assert normalizer.normalize("1K0.615.301") == "1K0615301"

    def test_invalid_oe_all_zeros(self, normalizer):
        """全 0 OE 标记无效"""
        assert normalizer.normalize("000") is None
        assert normalizer.normalize("OE-000") is None

    def test_empty_string(self, normalizer):
        """空字符串返回 None"""
        assert normalizer.normalize("") is None
        assert normalizer.normalize("   ") is None

    def test_get_oe_base(self, normalizer):
        """获取基号（去末尾字母）"""
        assert normalizer.get_oe_base("1K0615301AA") == "1K0615301"
        assert normalizer.get_oe_base("1K0615301") == "1K0615301"
        # ABC 全为字母，去末尾字母后为空 → None
        assert normalizer.get_oe_base("ABC") is None

    def test_is_valid(self, normalizer):
        """判断 OE 有效性"""
        assert normalizer.is_valid("0986479012") is True
        assert normalizer.is_valid("000") is False
        assert normalizer.is_valid("") is False


class TestFitmentNormalizer:
    """车型适配归一化测试（ADR-21）"""

    @pytest.fixture
    def normalizer(self, mock_settings):
        return FitmentNormalizer()

    def test_normalize_brand_chinese(self, normalizer):
        """中文 brand 映射"""
        assert normalizer.normalize_brand("大众") == "VW"
        assert normalizer.normalize_brand("宝马") == "BMW"

    def test_normalize_brand_english(self, normalizer):
        """英文 brand 映射"""
        assert normalizer.normalize_brand("Volkswagen") == "VW"
        assert normalizer.normalize_brand("Mercedes-Benz") == "MB"

    def test_normalize_brand_case_insensitive(self, normalizer):
        """忽略大小写匹配"""
        assert normalizer.normalize_brand("vw") == "VW"

    def test_normalize_brand_unknown(self, normalizer):
        """未知 brand 返回大写"""
        assert normalizer.normalize_brand("UnknownBrand") == "UNKNOWNBRAND"
        assert normalizer.normalize_brand("") == "UNKNOWN"

    def test_normalize_engine_code(self, normalizer):
        """engine_code 大写 + 去空格"""
        assert normalizer.normalize_engine_code("aum") == "AUM"
        assert normalizer.normalize_engine_code("A U M") == "AUM"
        assert normalizer.normalize_engine_code(None) is None

    def test_normalize_model(self, normalizer):
        """model 压缩空格"""
        assert normalizer.normalize_model("  Golf   IV  ") == "Golf IV"

    def test_normalize_record(self, normalizer):
        """完整记录归一化"""
        record = {
            "brand": "大众",
            "series": "帕萨特",
            "model": "  B5  ",
            "engineCode": "aum",
            "yearStart": 2000,
            "yearEnd": 2005,
            "chassisCode": "3B",
            "note": "",
        }
        result = normalizer.normalize_record(record)
        assert result["brand"] == "VW"
        assert result["series"] == "帕萨特"
        assert result["model"] == "B5"
        assert result["engine_code"] == "AUM"
        assert result["year_start"] == 2000
        assert result["year_end"] == 2005
