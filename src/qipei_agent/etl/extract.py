# plan-P1-1,P2-4
"""ETL 抽取：从 PIM / 金蝶拉取数据（ADR-20 / ADR-16 / ADR-32）"""

from typing import Optional

from qipei_agent.integration.kingdee import KingdeeClient
from qipei_agent.integration.pim import PIMClient
from qipei_agent.shared.errors import get_logger

logger = get_logger(__name__)


async def extract_pim_oe_vehicle(
    pim_client: PIMClient,
    material_code: Optional[str] = None,
    oe_no: Optional[str] = None,
) -> list[dict]:
    """从 PIM 拉取 OE/车型主数据（全量或按条件）"""
    all_records = []
    page = 1
    page_size = 500

    while True:
        result = await pim_client.get_oe_vehicle(
            material_code=material_code,
            oe_no=oe_no,
            page=page,
            page_size=page_size,
        )
        records = result.get("records", [])
        all_records.extend(records)

        if len(records) < page_size:
            break
        page += 1

    logger.info(f"PIM 拉取完成：{len(all_records)} 条记录")
    return all_records


async def extract_kingdee_stock(kingdee_client: KingdeeClient, sku_code: Optional[str] = None) -> list[dict]:
    """从金蝶拉取库存数据（FAVAILABLEQTY）"""
    filter_str = f"FMATERIALID='{sku_code}'" if sku_code else ""
    result = await kingdee_client.execute_bill_query(
        "STK_INVENTORY",
        ["FMATERIALID", "FAVAILABLEQTY"],
        filter_string=filter_str,
        limit=500,
    )
    rows = result.get("rows", [])
    logger.info(f"金蝶库存拉取完成：{len(rows)} 条记录")
    return rows


async def extract_kingdee_price(kingdee_client: KingdeeClient) -> list[dict]:
    """从金蝶拉取分级价数据（SAL_PRICEBASE）"""
    result = await kingdee_client.query_price_base()
    rows = result.get("rows", [])
    logger.info(f"金蝶分级价拉取完成：{len(rows)} 条记录")
    return rows


async def extract_kingdee_supplier_material(kingdee_client: KingdeeClient) -> list[dict]:
    """从金蝶拉取供应商物料数据（BD_MATERIALSUPPLIER）"""
    result = await kingdee_client.query_material_supplier()
    rows = result.get("rows", [])
    logger.info(f"金蝶供应商物料拉取完成：{len(rows)} 条记录")
    return rows


async def extract_kingdee_purchase_order(kingdee_client: KingdeeClient) -> list[dict]:
    """从金蝶拉取采购订单数据（PUR_PURCHASEORDER）"""
    result = await kingdee_client.query_purchase_order()
    rows = result.get("rows", [])
    logger.info(f"金蝶采购订单拉取完成：{len(rows)} 条记录")
    return rows


async def extract_kingdee_supplier_month_max(kingdee_client: KingdeeClient) -> list[dict]:
    """从金蝶拉取历史月最大供货量（V_MATERIAL_SUPPLIER_MONTH_MAX_QTY）"""
    result = await kingdee_client.execute_bill_query(
        "V_MATERIAL_SUPPLIER_MONTH_MAX_QTY",
        ["FMATERIALID", "FSUPPLIERID", "FMAX_MONTH_QTY"],
        limit=500,
    )
    rows = result.get("rows", [])
    logger.info(f"金蝶月最大供货量拉取完成：{len(rows)} 条记录")
    return rows


async def extract_kingdee_customer(kingdee_client: KingdeeClient) -> list[dict]:
    """从金蝶拉取客户数据（BD_CUSTOMER）"""
    result = await kingdee_client.query_customer()
    rows = result.get("rows", [])
    logger.info(f"金蝶客户拉取完成：{len(rows)} 条记录")
    return rows
