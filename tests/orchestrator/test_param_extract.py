# plan-P4-3
"""参数抽取测试：OE/品牌/年份/数量规则抽取"""



from qipei_agent.orchestrator.param_extract import (
    extract_brand,
    extract_oe,
    extract_params,
    extract_qty,
    extract_year,
    normalize_brand,
)

# param_extract 不依赖 get_settings，无需 mock


# ─── OE 抽取 ───

def test_extract_oe_simple():
    assert extract_oe("查 OE 6Q0820803C") == "6Q0820803C"


def test_extract_oe_with_prefix():
    assert extract_oe("OE:1K0615301AA") == "1K0615301AA"


def test_extract_oe_with_separator():
    assert extract_oe("OE 6Q0-820-803C") == "6Q0-820-803C"


def test_extract_oe_none():
    assert extract_oe("大众高尔夫刹车片") is None


# ─── 品牌抽取 ───

def test_extract_brand_chinese():
    assert extract_brand("大众高尔夫") == "VW"


def test_extract_brand_english():
    assert extract_brand("Toyota Camry") == "TOYOTA"


def test_extract_brand_none():
    assert extract_brand("刹车片配件") is None


# ─── 年份抽取 ───

def test_extract_year():
    assert extract_year("大众高尔夫 2005 款") == 2005


def test_extract_year_1990s():
    assert extract_year("宝马 3 系 1998 年") == 1998


def test_extract_year_none():
    assert extract_year("大众高尔夫") is None


# ─── 数量抽取 ───

def test_extract_qty():
    assert extract_qty("我要 100 件") == 100


def test_extract_qty_with_unit():
    assert extract_qty("需要 50 套") == 50


def test_extract_qty_none():
    assert extract_qty("查 OE 号") is None


# ─── 品牌归一化 ───

def test_normalize_brand_vw():
    assert normalize_brand("大众") == "VW"
    assert normalize_brand("Volkswagen") == "VW"
    assert normalize_brand("vw") == "VW"


def test_normalize_brand_mb():
    assert normalize_brand("奔驰") == "MB"
    assert normalize_brand("Mercedes-Benz") == "MB"


# ─── 完整参数抽取 ───

def test_extract_params_oe_query():
    params = extract_params("查 OE 1K0615301AA", "oe_query")
    assert params["oe_codes"] == "1K0615301AA"
    assert params["brand"] is None
    assert params["year"] is None


def test_extract_params_fitment_query():
    params = extract_params("大众高尔夫 2005 刹车片", "fitment_query")
    assert params["brand"] == "VW"
    assert params["year"] == 2005


def test_extract_params_with_qty():
    params = extract_params("OE 6Q0820803C 要 100 件", "oe_query")
    assert params["oe_codes"] == "6Q0820803C"
    assert params["qty"] == 100


def test_extract_params_negative_qty():
    params = extract_params("要 0 件", "oe_query")
    assert params["qty"] is None  # 校验：数量必须为正整数
