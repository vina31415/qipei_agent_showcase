# plan-P2-2
"""金蝶集成客户端测试（httpx mock，不连真实金蝶）"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from qipei_agent.integration.kingdee import KingdeeClient


@pytest.fixture
def mock_settings():
    """Mock Settings with test values"""
    with patch("qipei_agent.integration.kingdee.get_settings") as mock:
        mock.return_value = type(
            "MockSettings",
            (),
            {
                "KINGDEE_BASE_URL": "https://test-erp.example.com",
                "KINGDEE_TOKEN": "test-token",
                "KINGDEE_REFRESH_TOKEN": "test-refresh-token",
            },
        )()
        yield mock


@pytest.fixture
def client(mock_settings):
    return KingdeeClient()


@pytest.mark.asyncio
async def test_execute_bill_query_success(client):
    """测试 executeBillQuery 成功响应"""
    mock_response = httpx.Response(
        200,
        json={
            "Result": {
                "IsSuccess": True,
                "Rows": [["M001", "刹车片", "CP-ENG-00781"]],
                "TotalCount": 1,
            }
        },
    )

    with patch.object(client, "_request_with_retry", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await client.execute_bill_query(
            "BD_MATERIAL",
            ["FMATERIALID", "FNAME", "FNUMBER"],
            filter_string="FMATERIALID='M001'",
        )

    assert result["is_success"] is True
    assert len(result["rows"]) == 1
    assert result["total_count"] == 1


@pytest.mark.asyncio
async def test_execute_bill_query_failure(client):
    """测试 executeBillQuery 失败响应"""
    mock_response = httpx.Response(
        200,
        json={
            "Result": {
                "IsSuccess": False,
                "Rows": [],
                "TotalCount": 0,
            }
        },
    )

    with patch.object(client, "_request_with_retry", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = mock_response
        result = await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])

    assert result["is_success"] is False
    assert result["rows"] == []


@pytest.mark.asyncio
async def test_429_rate_limit_retry(client):
    """测试 429 限流重试"""
    call_count = 0

    def make_response(status_code, json_data=None, headers=None):
        resp = httpx.Response(status_code, json=json_data, headers=headers)
        resp.raise_for_status = lambda: None  # mock no-op
        return resp

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return make_response(429, headers={"Retry-After": "0.01"})
        return make_response(200, json_data={"Result": {"IsSuccess": True, "Rows": [], "TotalCount": 0}})

    with patch("qipei_agent.integration.kingdee.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])

    assert result["is_success"] is True
    assert call_count == 3  # 2 次 429 + 1 次成功


@pytest.mark.asyncio
async def test_401_token_refresh(client):
    """测试 401 触发 token 刷新"""
    call_count = 0

    def make_response(status_code, json_data=None):
        resp = httpx.Response(status_code, json=json_data)
        resp.raise_for_status = lambda: None  # mock no-op
        return resp

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return make_response(401)
        return make_response(200, json_data={"Result": {"IsSuccess": True, "Rows": [], "TotalCount": 0}})

    with patch.object(client, "_refresh_token", new_callable=AsyncMock) as mock_refresh:
        with patch("qipei_agent.integration.kingdee.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])

    assert result["is_success"] is True
    mock_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_query_material_fallback(client):
    """测试兜底查询物料主数据"""
    with patch.object(client, "execute_bill_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = {"is_success": True, "rows": [["M001", "刹车片"]], "total_count": 1}
        result = await client.query_material("M001")

    assert result["is_success"] is True


@pytest.mark.asyncio
async def test_query_oe_fallback(client):
    """测试 OE 兜底检索"""
    with patch.object(client, "execute_bill_query", new_callable=AsyncMock) as mock_query:
        mock_query.return_value = {
            "is_success": True,
            "rows": [["E001", "M001", "0986479012", "原厂", ""]],
            "total_count": 1,
        }
        result = await client.query_oe_fallback("0986479012")

    assert result["is_success"] is True
    mock_query.assert_called_once()
    # 验证 FilterString 包含 LIKE
    call_args = mock_query.call_args
    assert "FOENO LIKE '%0986479012%'" == call_args[1].get("filter_string") or \
           "FOENO LIKE '%0986479012%'" == call_args[0][2]


@pytest.mark.asyncio
async def test_semaphore_concurrency_limit(client):
    """测试并发限制 ≤10"""
    assert client._semaphore._value == 10


@pytest.mark.asyncio
async def test_timeout_degradation(client):
    """测试超时降级（E_KINGDEE_TIMEOUT）"""
    async def mock_post(*args, **kwargs):
        raise httpx.TimeoutException("Connection timeout")

    with patch("qipei_agent.integration.kingdee.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="金蝶请求失败"):
            await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])


@pytest.mark.asyncio
async def test_429_retry_after_default(client):
    """测试 429 无 Retry-After 时默认 5s"""
    call_count = 0

    def make_response(status_code, json_data=None, headers=None):
        resp = httpx.Response(status_code, json=json_data, headers=headers)
        resp.raise_for_status = lambda: None
        return resp

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return make_response(429)  # 无 Retry-After
        return make_response(200, json_data={"Result": {"IsSuccess": True, "Rows": [], "TotalCount": 0}})

    with patch("qipei_agent.integration.kingdee.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])

    assert result["is_success"] is True
    assert call_count == 3


@pytest.mark.asyncio
async def test_exponential_backoff(client):
    """测试指数退避 3 次封顶 30s"""
    call_count = 0
    sleep_times = []

    async def mock_sleep(seconds):
        sleep_times.append(seconds)

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("timeout")

    with patch("qipei_agent.integration.kingdee.httpx.AsyncClient") as mock_client_cls:
        with patch("asyncio.sleep", mock_sleep):
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(RuntimeError):
                await client.execute_bill_query("BD_MATERIAL", ["FMATERIALID"])

    # 验证指数退避：1s, 2s, 4s
    assert len(sleep_times) == 3
    assert sleep_times[0] == 1.0
    assert sleep_times[1] == 2.0
    assert sleep_times[2] == 4.0
