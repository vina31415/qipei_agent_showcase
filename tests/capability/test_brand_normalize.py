# plan-P5-2
"""brand 归一化测试（ADR-24/21）"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from qipei_agent.etl.normalize_fitment import FitmentNormalizer

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


@pytest.fixture
def normalizer():
    """创建归一化器（使用真实配置）"""
    with open(CONFIG_DIR / "brand_normalize.yaml", encoding="utf-8") as f:
        brand_map = yaml.safe_load(f)
    with patch("qipei_agent.etl.normalize_fitment.get_settings") as mock_gs:
        mock_settings = MagicMock()
        mock_settings.brand_normalize_config = brand_map
        mock_gs.return_value = mock_settings
        return FitmentNormalizer()


@pytest.fixture
def brand_map():
    """加载 brand_normalize.yaml"""
    with open(CONFIG_DIR / "brand_normalize.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class TestBrandMapping:
    """逐键值断言（brand_normalize.yaml 全部键）"""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            # 大众
            ("大众", "VW"),
            ("Volkswagen", "VW"),
            ("vw", "VW"),
            # 宝马
            ("宝马", "BMW"),
            ("B.M.W", "BMW"),
            # 奔驰
            ("奔驰", "MB"),
            ("Mercedes-Benz", "MB"),
            ("Mercedes", "MB"),
            # 丰田
            ("丰田", "TOYOTA"),
            ("Toyota", "TOYOTA"),
            # 本田
            ("本田", "HONDA"),
            ("Honda", "HONDA"),
            # 日产
            ("日产", "NISSAN"),
            ("Nissan", "NISSAN"),
            # 奥迪
            ("奥迪", "AUDI"),
            ("Audi", "AUDI"),
            # 博世
            ("博世", "BOSCH"),
            ("Bosch", "BOSCH"),
            # 德尔福
            ("德尔福", "DELPHI"),
            ("Delphi", "DELPHI"),
            # 大陆
            ("大陆", "CONTINENTAL"),
            ("Continental", "CONTINENTAL"),
            # 采埃孚
            ("采埃孚", "ZF"),
            ("Z.F", "ZF"),
            # 其他品牌
            ("现代", "HYUNDAI"),
            ("起亚", "KIA"),
            ("马自达", "MAZDA"),
            ("三菱", "MITSUBISHI"),
            ("福特", "FORD"),
            ("菲亚特", "FIAT"),
            ("标致", "PEUGEOT"),
            ("雪铁龙", "CITROEN"),
        ],
    )
    def test_brand_mapping(self, normalizer, raw, expected):
        """逐键值断言 brand 映射"""
        assert normalizer.normalize_brand(raw) == expected


class TestBrandFallback:
    """兜底测试"""

    def test_empty_string_to_unknown(self, normalizer):
        """空字符串→UNKNOWN"""
        assert normalizer.normalize_brand("") == "UNKNOWN"

    def test_none_to_unknown(self, normalizer):
        """None→UNKNOWN"""
        assert normalizer.normalize_brand(None) == "UNKNOWN"

    def test_unknown_brand_uppercase(self, normalizer):
        """未知品牌→大写"""
        assert normalizer.normalize_brand("unknown_brand") == "UNKNOWN_BRAND"


class TestCaseInsensitive:
    """大小写/别名覆盖测试"""

    def test_lowercase_vw(self, normalizer):
        """小写 vw→VW"""
        assert normalizer.normalize_brand("vw") == "VW"

    def test_mixed_case_mercedes(self, normalizer):
        """混合大小写 mercedes→MB"""
        assert normalizer.normalize_brand("mercedes") == "MB"

    def test_mixed_case_toyota(self, normalizer):
        """混合大小写 toyota→TOYOTA"""
        assert normalizer.normalize_brand("toyota") == "TOYOTA"


class TestBrandYAMLCoverage:
    """确认 YAML 全部键被覆盖"""

    def test_all_yaml_keys_tested(self, brand_map):
        """确认所有 YAML 键都有对应测试"""
        tested_keys = {
            "大众", "Volkswagen", "vw",
            "宝马", "B.M.W",
            "奔驰", "Mercedes-Benz", "Mercedes",
            "丰田", "Toyota",
            "本田", "Honda",
            "日产", "Nissan",
            "奥迪", "Audi",
            "博世", "Bosch",
            "德尔福", "Delphi",
            "大陆", "Continental",
            "采埃孚", "Z.F",
            "现代", "起亚", "马自达", "三菱",
            "福特", "菲亚特", "标致", "雪铁龙",
            "",  # 兜底空字符串
        }
        yaml_keys = set(brand_map.keys())
        # 注意：null 键在 YAML 中会被解析为 None
        yaml_keys_without_none = {k for k in yaml_keys if k is not None}
        assert tested_keys >= yaml_keys_without_none, (
            f"未覆盖的 YAML 键: {yaml_keys_without_none - tested_keys}"
        )
