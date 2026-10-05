# plan-P1-1,P2-2
"""金蝶集成客户端：executeBillQuery + 鉴权刷新 + 兜底表单 + OE 兜底（只读）"""

import asyncio
import time
from typing import Optional

import httpx

from qipei_agent.shared.config import get_settings
from qipei_agent.shared.errors import get_logger

logger = get_logger(__name__)

# 金蝶 executeBillQuery 端点（ADR-16）
EXECUTE_BILL_QUERY_PATH = "/k3cloudapi/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery"

# Token 刷新端点（ADR-29）
REFRESH_TOKEN_PATH = "/api/Kingdee.BOS.WebApi.ServicesStub.AuthService.RefreshToken"

# 5 兜底表单（ADR-28）
FALLBACK_FORMS = {
    "BD_MATERIAL": ["FMATERIALID", "FNAME", "FNUMBER", "FLEADTIME"],
    "BD_CUSTOMER": ["FCUSTID", "FNUMBER", "FNAME", "FCUSTLEVELID", "FCURRENCYID"],
    "BD_MATERIALSUPPLIER": [
        "FMATERIALID", "FSUPPLIERID", "FISDEFAULTSUPPLIER", "FLEADTIMESUPP",
    ],
    "PUR_PURCHASEORDER": [
        "FID", "FBillNo", "FMATERIALID", "FPLANARRIVALDATE",
        "FQTY", "FRECEIVEQTY", "FDOCUMENTSTATUS",
    ],
    "SAL_PRICEBASE": [
        "FMATERIALID", "FCUSTLEVELID", "FQTYLOW", "FQTYHIGH",
        "FPRICE", "FISINCLUDETAX", "FTAXRATE", "FCURRENCYID",
    ],
}

# OE 兜底表单（ADR-35）
OE_FALLBACK_FORM_ID = "BD_MATERIAL_OE_EXT"
OE_FALLBACK_FIELDS = ["FID", "FMATERIALID", "FOENO", "FOETYPE", "FREMARK"]


class KingdeeClient:
    """金蝶集成客户端（只读，executeBillQuery）"""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.KINGDEE_BASE_URL
        self._token = token or settings.KINGDEE_TOKEN
        self._refresh_token = refresh_token or settings.KINGDEE_REFRESH_TOKEN
        self._token_expiry: Optional[float] = None
        self._semaphore = asyncio.Semaphore(10)  # 并发 ≤10（ADR-16）

    @property
    def token(self) -> str:
        return self._token

    async def _refresh_token(self) -> None:
        """刷新金蝶 KDSpaceToken（ADR-29）"""
        url = f"{self.base_url}{REFRESH_TOKEN_PATH}"
        body = {"refreshToken": self._refresh_token}
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            self._token = data.get("access_token") or data.get("AccessToken", "")
            self._refresh_token = data.get("refresh_token") or data.get("RefreshToken", self._refresh_token)
            expires_in = data.get("expires_in") or data.get("ExpiresIn", 7200)
            self._token_expiry = time.time() + expires_in
            logger.info("金蝶 token 刷新成功")

    async def _ensure_token(self) -> None:
        """确保 token 有效，过期则刷新"""
        if self._token_expiry and time.time() >= self._token_expiry:
            await self._refresh_token()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        json_body: dict,
        max_retries: int = 3,
        backoff_initial: float = 1.0,
        backoff_factor: float = 2.0,
        backoff_max: float = 30.0,
    ) -> httpx.Response:
        """带重试/退避/429 处理的 HTTP 请求（ADR-22/23）"""
        backoff = backoff_initial
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, json=json_body, timeout=10)

                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "5")
                    wait = float(retry_after)
                    logger.warning(f"金蝶 429 限流，等待 {wait}s 后重试（第 {attempt + 1} 次）")
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
                    logger.warning(f"金蝶请求失败（第 {attempt + 1} 次重试）：{e}")
                    await asyncio.sleep(min(backoff, backoff_max))
                    backoff *= backoff_factor
                else:
                    logger.error(f"金蝶请求失败，已达最大重试次数：{e}")

        raise RuntimeError(f"金蝶请求失败，已重试 {max_retries} 次") from last_error

    async def execute_bill_query(
        self,
        form_id: str,
        field_keys: list[str],
        filter_string: str = "",
        order_string: str = "",
        top_row_count: int = 0,
        start_row: int = 0,
        limit: int = 20,
    ) -> dict:
        """执行金蝶 executeBillQuery（ADR-16）"""
        await self._ensure_token()

        url = f"{self.base_url}{EXECUTE_BILL_QUERY_PATH}"
        body = {
            "FormId": form_id,
            "FieldKeys": field_keys,
            "FilterString": filter_string,
            "OrderString": order_string,
            "TopRowCount": top_row_count,
            "StartRow": start_row,
            "Limit": limit,
        }

        async with self._semaphore:
            resp = await self._request_with_retry("POST", url, body)
            result = resp.json()

        is_success = result.get("Result", {}).get("IsSuccess", False)
        rows = result.get("Result", {}).get("Rows", [])
        total_count = result.get("Result", {}).get("TotalCount", 0)

        return {
            "is_success": is_success,
            "rows": rows,
            "total_count": total_count,
        }

    # ─── 5 兜底表单查询（ADR-28） ───

    async def query_material(self, material_id: str = "", limit: int = 20) -> dict:
        """兜底查询物料主数据 BD_MATERIAL"""
        filter_str = f"FMATERIALID='{material_id}'" if material_id else ""
        return await self.execute_bill_query("BD_MATERIAL", FALLBACK_FORMS["BD_MATERIAL"], filter_str, limit=limit)

    async def query_customer(self, customer_id: str = "", limit: int = 20) -> dict:
        """兜底查询客户主数据 BD_CUSTOMER"""
        filter_str = f"FCUSTID='{customer_id}'" if customer_id else ""
        return await self.execute_bill_query("BD_CUSTOMER", FALLBACK_FORMS["BD_CUSTOMER"], filter_str, limit=limit)

    async def query_material_supplier(self, material_id: str = "", limit: int = 20) -> dict:
        """兜底查询物料供应商关联 BD_MATERIALSUPPLIER"""
        filter_str = f"FMATERIALID='{material_id}'" if material_id else ""
        return await self.execute_bill_query(
            "BD_MATERIALSUPPLIER",
            FALLBACK_FORMS["BD_MATERIALSUPPLIER"],
            filter_str,
            limit=limit,
        )

    async def query_purchase_order(self, material_id: str = "", limit: int = 20) -> dict:
        """兜底查询采购订单 PUR_PURCHASEORDER"""
        filter_str = f"FMATERIALID='{material_id}'" if material_id else ""
        return await self.execute_bill_query(
            "PUR_PURCHASEORDER",
            FALLBACK_FORMS["PUR_PURCHASEORDER"],
            filter_str,
            limit=limit,
        )

    async def query_price_base(self, material_id: str = "", limit: int = 20) -> dict:
        """兜底查询销售价格本 SAL_PRICEBASE"""
        filter_str = f"FMATERIALID='{material_id}'" if material_id else ""
        return await self.execute_bill_query("SAL_PRICEBASE", FALLBACK_FORMS["SAL_PRICEBASE"], filter_str, limit=limit)

    # ─── OE 兜底检索（ADR-35） ───

    async def query_oe_fallback(self, oe: str, start_row: int = 0, limit: int = 20) -> dict:
        """OE 兜底检索：BD_MATERIAL_OE_EXT（FOENO LIKE '%{oe}%'）"""
        filter_str = f"FOENO LIKE '%{oe}%'"
        return await self.execute_bill_query(
            OE_FALLBACK_FORM_ID,
            OE_FALLBACK_FIELDS,
            filter_str,
            start_row=start_row,
            limit=limit,
        )

