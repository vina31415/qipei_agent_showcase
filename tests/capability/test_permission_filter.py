# plan-P3-8
"""权限过滤测试"""

from unittest.mock import MagicMock, patch

import pytest

from qipei_agent.capability.permission_filter import apply_permission_filter

SALES_FIELDS = [
    "sku_code", "name", "price", "lead_time",
    "supplier_note", "alternatives", "on_hand",
    "risk_level", "risk_hint", "customer_tier", "pos",
]
CS_VISIBLE = [
    "sku_code", "name", "price", "lead_time",
    "on_hand", "risk_level", "risk_hint", "customer_tier",
]
CS_HIDDEN = ["supplier_note", "alternatives", "pos"]
WH_VISIBLE = ["sku_code", "name", "on_hand"]
WH_HIDDEN = [
    "price", "lead_time", "supplier_note", "alternatives",
    "risk_level", "risk_hint", "customer_tier", "pos",
]


@pytest.fixture
def mock_settings():
    with patch("qipei_agent.shared.permissions.get_settings") as m:
        cfg = MagicMock()
        cfg.permission_config = {"roles": {
            "sales": {"name": "业务员", "visible_fields": SALES_FIELDS},
            "merchandiser": {"name": "跟单", "visible_fields": SALES_FIELDS},
            "cs": {"name": "售后", "visible_fields": CS_VISIBLE, "hidden_fields": CS_HIDDEN},
            "warehouse": {"name": "仓库", "visible_fields": WH_VISIBLE, "hidden_fields": WH_HIDDEN},
        }}
        m.return_value = cfg
        yield cfg


class TestPermissionFilter:
    def test_warehouse_no_price(self, mock_settings):
        """仓库角色查同一 SKU 价格字段不出现"""
        resp = {"skus": [{"sku_code": "SKU001", "name": "刹车片", "price": 100.0, "lead_time": 5}]}
        result = apply_permission_filter("warehouse", resp)
        sku = result["skus"][0]
        assert "price" not in sku
        assert "lead_time" not in sku
        assert sku["sku_code"] == "SKU001"

    def test_cs_no_supplier_note(self, mock_settings):
        """售后无供应商备注/备选交期"""
        resp = {"skus": [{"sku_code": "SKU001", "supplier_note": "备注", "alternatives": ["SUP2"]}]}
        result = apply_permission_filter("cs", resp)
        sku = result["skus"][0]
        assert "supplier_note" not in sku
        assert "alternatives" not in sku
        assert sku["sku_code"] == "SKU001"

    def test_sales_full_access(self, mock_settings):
        """业务员全量"""
        resp = {"skus": [{"sku_code": "SKU001", "price": 100.0, "lead_time": 5,
                          "supplier_note": "备注", "alternatives": ["SUP2"]}]}
        result = apply_permission_filter("sales", resp)
        sku = result["skus"][0]
        assert sku["price"] == 100.0
        assert sku["lead_time"] == 5
        assert sku["supplier_note"] == "备注"

    def test_merchandiser_full_access(self, mock_settings):
        """跟单全量"""
        resp = {"skus": [{"sku_code": "SKU001", "price": 100.0, "lead_time": 5,
                          "supplier_note": "备注", "alternatives": ["SUP2"]}]}
        result = apply_permission_filter("merchandiser", resp)
        sku = result["skus"][0]
        assert sku["price"] == 100.0
        assert sku["lead_time"] == 5
        assert sku["supplier_note"] == "备注"

    def test_unknown_role(self, mock_settings):
        """未知角色返回空"""
        resp = {"skus": [{"sku_code": "SKU001", "price": 100.0}]}
        result = apply_permission_filter("unknown", resp)
        assert result["skus"][0] == {}

    def test_warehouse_full_response(self, mock_settings):
        """仓库角色：仅可见库存/SKU/品名"""
        resp = {"skus": [{
            "sku_code": "SKU001", "name": "刹车片", "on_hand": 50,
            "price": 100.0, "lead_time": 5, "supplier_note": "备注",
            "alternatives": [{"supplier_id": "SUP2"}],
            "risk_level": "medium", "risk_hint": "提示",
            "customer_tier": "A", "pos": [],
        }]}
        result = apply_permission_filter("warehouse", resp)
        sku = result["skus"][0]
        assert set(sku.keys()) == {"sku_code", "name", "on_hand"}

    def test_cs_visible_fields(self, mock_settings):
        """售后角色：可见价格/交期/风险，隐藏供应商信息"""
        resp = {"skus": [{
            "sku_code": "SKU001", "name": "刹车片", "price": 100.0,
            "lead_time": 5, "on_hand": 50, "risk_level": "medium",
            "risk_hint": "提示", "customer_tier": "A",
            "supplier_note": "备注", "alternatives": [{"supplier_id": "SUP2"}],
            "pos": [{"supplier_id": "SUP1"}],
        }]}
        result = apply_permission_filter("cs", resp)
        sku = result["skus"][0]
        for field in CS_VISIBLE:
            assert field in sku, f"{field} should be visible for cs"
        for field in CS_HIDDEN:
            assert field not in sku, f"{field} should be hidden for cs"

    def test_sales_all_fields_visible(self, mock_settings):
        """业务员：所有字段可见"""
        resp = {"skus": [{
            "sku_code": "SKU001", "name": "刹车片", "price": 100.0,
            "lead_time": 5, "on_hand": 50, "risk_level": "medium",
            "risk_hint": "提示", "customer_tier": "A",
            "supplier_note": "备注", "alternatives": [{"supplier_id": "SUP2"}],
            "pos": [{"supplier_id": "SUP1"}],
        }]}
        result = apply_permission_filter("sales", resp)
        sku = result["skus"][0]
        for field in SALES_FIELDS:
            assert field in sku, f"{field} should be visible for sales"

    def test_merchandiser_all_fields_visible(self, mock_settings):
        """跟单：所有字段可见"""
        resp = {"skus": [{
            "sku_code": "SKU001", "name": "刹车片", "price": 100.0,
            "lead_time": 5, "on_hand": 50, "risk_level": "medium",
            "risk_hint": "提示", "customer_tier": "A",
            "supplier_note": "备注", "alternatives": [{"supplier_id": "SUP2"}],
            "pos": [{"supplier_id": "SUP1"}],
        }]}
        result = apply_permission_filter("merchandiser", resp)
        sku = result["skus"][0]
        for field in SALES_FIELDS:
            assert field in sku, f"{field} should be visible for merchandiser"

    def test_filter_applied_at_capability_layer(self, mock_settings):
        """验证过滤发生在能力层（非编排层）"""
        # 模拟能力层返回的完整响应
        full_resp = {"skus": [{
            "sku_code": "SKU001", "name": "刹车片", "price": 100.0,
            "lead_time": 5, "supplier_note": "内部备注",
        }]}
        # 仓库角色过滤后
        result = apply_permission_filter("warehouse", full_resp)
        # 确认敏感字段已移除
        assert "price" not in result["skus"][0]
        assert "lead_time" not in result["skus"][0]
        assert "supplier_note" not in result["skus"][0]
        # 原始响应也被修改（原地过滤）
        assert "price" not in full_resp["skus"][0]
