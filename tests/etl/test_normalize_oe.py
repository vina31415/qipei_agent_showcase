# plan-P3-2, plan-P5-1
"""normalize_oe 工具测试（26 样本 + 前缀/分隔符/前导零/大写变体 + 全 0 无效）"""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from qipei_agent.capability.normalize_oe import get_normalizer, handle_normalize_oe

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock Settings with test config"""
    with patch("qipei_agent.etl.normalize_oe.get_settings") as mock_gs:
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
            },
        )()
        mock_gs.return_value = mock_settings_obj
        yield mock_settings_obj


class TestNormalizeOE26Samples:
    """26 条业务样本测试（oe_test_samples.md）"""

    @pytest.mark.parametrize(
        "oe_raw,expected",
        [
            ("6Q0820803C", "6Q0820803C"),
            ("0986479012", "986479012"),
            ("43206-3JA0A", "432063JA0A"),
            ("LR020365", "LR020365"),
            ("1K0615301AA", "1K0615301AA"),
            ("2113200431", "2113200431"),
            ("90510950", "90510950"),
            ("0281002405", "281002405"),
            ("51750-2H000", "517502H000"),
            ("A2043200630", "A2043200630"),
            ("12637020", "12637020"),
            ("7L0615301", "7L0615301"),
            ("42535037", "42535037"),
            ("13717524465", "13717524465"),
            ("58101-2E000", "581012E000"),
            ("96409123", "96409123"),
            ("27700-2B700", "277002B700"),
            ("0445110247", "445110247"),
            ("31277354", "31277354"),
            ("8943768441", "8943768441"),
            ("A0004311200", "A0004311200"),
            ("7701208054", "7701208054"),
            ("16100-87J00", "1610087J00"),
            ("11377548388", "11377548388"),
            ("4681132AB", "4681132AB"),
            ("90467655", "90467655"),
        ],
    )
    def test_26_samples(self, oe_raw, expected):
        """26 条业务样本归一化"""
        result = handle_normalize_oe(oe_raw)
        assert result["oe_normalized"] == expected
        assert result["is_valid"] is True


class TestPrefixVariants:
    """前缀去除测试"""

    @pytest.mark.parametrize(
        "oe_raw,expected",
        [
            ("REF.NO.123456", "123456"),
            ("OEM#123456", "123456"),
            ("OEM-123456", "123456"),
            ("OE#0986479012", "986479012"),
            ("OE-0986479012", "986479012"),
            ("REF 123456", "123456"),
            ("NO.123456", "123456"),
            ("N°123456", "123456"),
            # 小写前缀也应去除
            ("oe-123456", "123456"),
            ("ref.no.123456", "123456"),
            # OEM123456 不应去前缀（1 是字母数字，不满足边界）
            ("OEM123456", "OEM123456"),
        ],
    )
    def test_prefix_removal(self, oe_raw, expected):
        result = handle_normalize_oe(oe_raw)
        assert result["oe_normalized"] == expected


class TestSeparatorRemoval:
    """分隔符去除测试"""

    @pytest.mark.parametrize(
        "oe_raw,expected",
        [
            ("1K0-615-301", "1K0615301"),
            ("1K0/615/301", "1K0615301"),
            ("1K0.615.301", "1K0615301"),
            ("1K0_615_301", "1K0615301"),
            ("0 986 479 012", "986479012"),
        ],
    )
    def test_separator_removal(self, oe_raw, expected):
        result = handle_normalize_oe(oe_raw)
        assert result["oe_normalized"] == expected


class TestLeadingZeroStripping:
    """前导零去除测试"""

    def test_pure_digit_strip(self):
        """纯数字去前导零"""
        result = handle_normalize_oe("0986479012")
        assert result["oe_normalized"] == "986479012"

    def test_no_strip_with_letters(self):
        """含字母不去前导零"""
        result = handle_normalize_oe("0A123")
        assert result["oe_normalized"] == "0A123"

    def test_all_zeros_invalid(self):
        """全 0 标记无效"""
        result = handle_normalize_oe("000")
        assert result["oe_normalized"] is None
        assert result["is_valid"] is False

    def test_single_zero_invalid(self):
        """单个 0 标记无效"""
        result = handle_normalize_oe("0")
        assert result["oe_normalized"] is None
        assert result["is_valid"] is False


class TestCaseVariants:
    """大小写变体测试"""

    def test_lowercase_to_uppercase(self):
        """小写转大写"""
        result = handle_normalize_oe("6q0820803c")
        assert result["oe_normalized"] == "6Q0820803C"

    def test_mixed_case(self):
        """混合大小写"""
        result = handle_normalize_oe("Lr020365")
        assert result["oe_normalized"] == "LR020365"


class TestVersionSuffix:
    """版本后缀测试（6Q0820803C ≠ 6Q0820803）"""

    def test_different_versions(self):
        """不同版本后缀应保留差异"""
        r1 = handle_normalize_oe("6Q0820803C")
        r2 = handle_normalize_oe("6Q0820803")
        assert r1["oe_normalized"] != r2["oe_normalized"]
        assert r1["oe_normalized"] == "6Q0820803C"
        assert r2["oe_normalized"] == "6Q0820803"


class TestInvalidInputs:
    """无效输入测试"""

    @pytest.mark.parametrize("oe_raw", ["", "   ", None])
    def test_empty_or_whitespace(self, oe_raw):
        result = handle_normalize_oe(oe_raw or "")
        assert result["oe_normalized"] is None
        assert result["is_valid"] is False


class TestGetNormalizerSingleton:
    """单例测试"""

    def test_singleton_returns_same_instance(self):
        n1 = get_normalizer()
        n2 = get_normalizer()
        assert n1 is n2


class TestOEFixtureYAML:
    """从 oe_samples.yaml fixture 加载测试（P5-1）"""

    @pytest.fixture(scope="class")
    def fixture_data(self):
        with open(FIXTURE_DIR / "oe_samples.yaml") as f:
            return yaml.safe_load(f)

    @pytest.mark.parametrize("sample", [s for s in yaml.safe_load(
        open(FIXTURE_DIR / "oe_samples.yaml")
    )["samples"]])
    def test_26_samples_from_yaml(self, sample):
        """26 条样本从 YAML fixture 加载断言"""
        result = handle_normalize_oe(sample["oe_raw"])
        assert result["oe_normalized"] == sample["expected"]
        assert result["is_valid"] == sample["is_valid"]

    @pytest.mark.parametrize("variant", [v for v in yaml.safe_load(
        open(FIXTURE_DIR / "oe_samples.yaml")
    )["variants"]])
    def test_variants_from_yaml(self, variant):
        """变体样本从 YAML fixture 加载断言"""
        result = handle_normalize_oe(variant["oe_raw"])
        assert result["oe_normalized"] == variant["expected"]
        assert result["is_valid"] == variant["is_valid"]
