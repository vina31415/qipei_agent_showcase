# plan-P1-1,P2-3
"""PIM 集成客户端：GET oe-vehicle + Bearer 鉴权刷新 + 重试/退避（只读）"""

import asyncio
import time
from typing import Optional

import httpx

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.errors import get_logger

logger = get_logger(__name__)

# PIM oe-vehicle 端点（ADR-20）
OE_VEHICLE_PATH = "/api/pim/adapt/oe-vehicle"

# PIM Token 刷新端点（ADR-29）
PIM_REFRESH_TOKEN_PATH = "/pim/api/v1/auth/refresh"


class PIMClient:
    """PIM 集成客户端（只读，GET oe-vehicle）"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.PIM_BASE_URL
        self._access_token = access_token or settings.PIM_ACCESS_TOKEN
        self._refresh_token = refresh_token or settings.PIM_REFRESH_TOKEN
        self._token_expiry: Optional[float] = None
        self._semaphore = asyncio.Semaphore(5)  # ETL 并发 ≤5（ADR-22）

    @property
    def access_token(self) -> str:
        return self._access_token

    async def _refresh_token(self) -> None:
        """刷新 PIM access_token（ADR-29）"""
        url = f"{self.base_url}{PIM_REFRESH_TOKEN_PATH}"
        body = {"refresh_token": self._refresh_token}
        headers = {"Authorization": f"Bearer {self._access_token}"}

        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, headers=headers, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data.get("access_token") or data.get("accessToken", "")
            self._refresh_token = data.get("refresh_token") or data.get("refreshToken", self._refresh_token)
            expires_in = data.get("expires_in") or data.get("expiresIn", 7200)
            self._token_expiry = time.time() + expires_in
            logger.info("PIM token 刷新成功")

    async def _ensure_token(self) -> None:
        """确保 token 有效，过期则刷新"""
        if self._token_expiry and time.time() >= self._token_expiry:
            await self._refresh_token()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        max_retries: int = 3,
        backoff_initial: float = 1.0,
        backoff_factor: float = 2.0,
        backoff_max: float = 30.0,
    ) -> httpx.Response:
        """带重试/退避/429 处理的 HTTP 请求（ADR-22）"""
        backoff = backoff_initial
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                headers = {"Authorization": f"Bearer {self._access_token}"}
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, params=params, headers=headers, timeout=10)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    wait = float(retry_after)
                    logger.warning(f"PIM 429 限流，等待 {wait}s 后重试（第 {attempt + 1} 次）")
                    await asyncio.sleep(wait)
                    continue

                if resp.status_code == 401:
                    await self._refresh_token()
                    continue

                resp.raise_for_status()
                return resp

            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < max_retries:
                    logger.warning(f"PIM 请求失败（第 {attempt + 1} 次重试）：{e}")
                    await asyncio.sleep(min(backoff, backoff_max))
                    backoff *= backoff_factor
                else:
                    logger.error(f"PIM 请求失败，已达最大重试次数：{e}")

        raise RuntimeError(f"PIM 请求失败，已重试 {max_retries} 次") from last_error

    async def get_oe_vehicle(
        self,
        material_code: Optional[str] = None,
        oe_no: Optional[str] = None,
        page: int = 1,
        page_size: int = 500,
    ) -> dict:
        """GET /api/pim/adapt/oe-vehicle（ADR-20）

        返回：{records: [{pimId, materialCode, productCategory, updateTime,
                        oeList[], vehicleAdaptList[]}], total, page, page_size}
        """
        await self._ensure_token()

        if page_size > 500:
            page_size = 500

        url = f"{self.base_url}{OE_VEHICLE_PATH}"
        params: dict = {"page": page, "pageSize": page_size}
        if material_code:
            params["materialCode"] = material_code
        if oe_no:
            params["oeNo"] = oe_no

        async with self._semaphore:
            resp = await self._request_with_retry("GET", url, params)
            result = resp.json()

        records = result.get("records", [])
        total = result.get("total", 0)

        return {
            "records": records,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
