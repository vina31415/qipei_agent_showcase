# plan-P3-1
"""能力层 main + 信封测试"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from qipei_agent.capability.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock Settings for normalize_oe handler"""
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


class TestEnvelope:
    """信封格式测试"""

    def test_success_envelope(self):
        """成功响应：{request_id, ok: true, data}"""
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"user_id": "u1", "role": "sales"},
            headers={"X-Request-Id": "test-rid-1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert "request_id" in body
        assert "data" in body
        assert "error" not in body

    def test_error_envelope_unknown_tool(self):
        """失败响应：{request_id, ok: false, error{code, message}}"""
        resp = client.post(
            "/api/v1/tools/unknown_tool",
            json={"user_id": "u1", "role": "sales"},
            headers={"X-Request-Id": "test-rid-2"},
        )
        assert resp.status_code == 200  # 业务错误仍返回 200
        body = resp.json()
        assert body["ok"] is False
        assert "error" in body
        assert body["error"]["code"] == "E_NOT_FOUND"
        assert "message" in body["error"]


class TestRequestIdPassthrough:
    """X-Request-Id 透传测试"""

    def test_request_id_from_header(self):
        """提供 X-Request-Id → 响应头与 body 中一致"""
        rid = "my-custom-rid"
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"user_id": "u1", "role": "sales"},
            headers={"X-Request-Id": rid},
        )
        assert resp.headers.get("X-Request-Id") == rid
        assert resp.json()["request_id"] == rid

    def test_request_id_generated(self):
        """未提供 X-Request-Id → 自动生成"""
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"user_id": "u1", "role": "sales"},
        )
        rid = resp.headers.get("X-Request-Id")
        assert rid is not None
        assert len(rid) > 0
        assert resp.json()["request_id"] == rid


class TestRequestValidation:
    """请求校验：user_id + role 必含"""

    def test_missing_user_id(self):
        """缺 user_id → 422"""
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"role": "sales"},
        )
        assert resp.status_code == 422

    def test_missing_role(self):
        """缺 role → 422"""
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"user_id": "u1"},
        )
        assert resp.status_code == 422

    def test_valid_request(self):
        """user_id + role 齐全 → 200"""
        resp = client.post(
            "/api/v1/tools/normalize_oe",
            json={"user_id": "u1", "role": "sales"},
        )
        assert resp.status_code == 200


class TestToolRouting:
    """工具路由测试"""

    def test_all_valid_tools(self):
        """6 个合法工具均返回成功"""
        tools = [
            "normalize_oe",
            "search_by_oe",
            "search_by_fitment",
            "get_stock",
            "get_price",
            "calc_lead_time",
        ]
        for tool in tools:
            resp = client.post(
                f"/api/v1/tools/{tool}",
                json={"user_id": "u1", "role": "sales"},
            )
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
            # 已实现的工具返回各自的数据，未实现的返回 placeholder
            data = resp.json()["data"]
            if "tool" in data:
                assert data["tool"] == tool

    def test_unknown_tool_returns_not_found(self):
        """未知工具 → E_NOT_FOUND"""
        resp = client.post(
            "/api/v1/tools/fake_tool",
            json={"user_id": "u1", "role": "sales"},
        )
        body = resp.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "E_NOT_FOUND"
