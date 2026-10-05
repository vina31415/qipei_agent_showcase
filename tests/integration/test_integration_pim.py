# plan-P2-3
"""PIM 集成客户端测试（httpx mock，不连真实 PIM）"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from qipei_agent.integration.pim import PIMClient


@pytest.fixture
def mock_settings():
    """Mock Settings with test values"""
    with patch("qipei_agent.integration.pim.get_settings") as mock:
        mock.return_value = type(
            "MockSettings",
            (),
            {
                "PIM_BASE_URL": "https://test-pim.example.com",
                "PIM_ACCESS_TOKEN": "test-pim-token",
                "PIM_REFRESH_TOKEN": "test-pim-refresh-token",
            },
        )()
        yield mock


@pytest.fixture
def client(mock_settings):
    return PIMClient()


def make_response(status_code, json_data=None, headers=None):
    """Helper to create mock httpx.Response with no-op raise_for_status"""
    resp = httpx.Response(status_code, json=json_data, headers=headers)
    resp.raise_for_status = lambda: None
    return resp


@pytest.mark.asyncio
async def test_get_oe_vehicle_success(client):
    """测试 get_oe_vehicle 成功响应"""
    mock_data = {
        "records": [
            {
                "pimId": "P001",
                "materialCode": "M001",
                "productCategory": "刹车系统",
                "updateTime": "2026-09-21T10:00:00Z",
                "oeList": [
                    {"oeRaw": "0986479012", "oeNormalized": "0986479012", "oeBrand": "BOSCH", "oeRemark": "原厂"}
                ],
                "vehicleAdaptList": [
                    {"brand": "大众", "series": "帕萨特", "model": "B5", "engineCode": "AWL",
                     "yearStart": 2000, "yearEnd": 2005, "chassisCode": "3B", "note": ""}
                ],
            }
        ],
        "total": 1,
    }

    async def mock_get(*args, **kwargs):
        return make_response(200, json_data=mock_data)

    with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await client.get_oe_vehicle(material_code="M001")

    assert len(result["records"]) == 1
    assert result["total"] == 1
    assert result["records"][0]["pimId"] == "P001"


@pytest.mark.asyncio
async def test_get_oe_vehicle_with_oe_no(client):
    """测试按 OE 号模糊查询"""
    mock_data = {"records": [], "total": 0}

    async def mock_get(*args, **kwargs):
        params = kwargs.get("params", {})
        assert "oeNo" in params
        assert params["oeNo"] == "0986479012"
        return make_response(200, json_data=mock_data)

    with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await client.get_oe_vehicle(oe_no="0986479012")


@pytest.mark.asyncio
async def test_get_oe_vehicle_page_size_capped(client):
    """测试 page_size 上限 500"""
    mock_data = {"records": [], "total": 0}

    async def mock_get(*args, **kwargs):
        params = kwargs.get("params", {})
        assert params["pageSize"] == 500
        return make_response(200, json_data=mock_data)

    with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        await client.get_oe_vehicle(page_size=1000)


@pytest.mark.asyncio
async def test_429_rate_limit_retry(client):
    """测试 429 限流重试"""
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return make_response(429, headers={"Retry-After": "0.01"})
        return make_response(200, json_data={"records": [], "total": 0})

    with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await client.get_oe_vehicle()

    assert result["total"] == 0
    assert call_count == 3  # 2 次 429 + 1 次成功


@pytest.mark.asyncio
async def test_401_token_refresh(client):
    """测试 401 触发 token 刷新"""
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_response(401)
        return make_response(200, json_data={"records": [], "total": 0})

    with patch.object(client, "_refresh_token", new_callable=AsyncMock) as mock_refresh:
        with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await client.get_oe_vehicle()

    assert result["total"] == 0
    mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_semaphore_concurrency_limit(client):
    """测试并发限制 ≤5"""
    assert client._semaphore._value == 5


@pytest.mark.asyncio
async def test_timeout_degradation(client):
    """测试超时降级（E_PIM_UNAVAILABLE）"""
    async def mock_get(*args, **kwargs):
        raise httpx.TimeoutException("Connection timeout")

    with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get = mock_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="PIM 请求失败"):
            await client.get_oe_vehicle()


@pytest.mark.asyncio
async def test_401_token_refresh_and_retry(client):
    """测试 401→token 刷新→重试"""
    call_count = 0

    async def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_response(401)
        return make_response(200, json_data={"records": [], "total": 0})

    with patch.object(client, "_refresh_token", new_callable=AsyncMock) as mock_refresh:
        with patch("qipei_agent.integration.pim.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await client.get_oe_vehicle()

    assert result["total"] == 0
    mock_refresh.assert_called_once()
    assert call_count == 2  # 1 次 401 + 1 次重试成功
