# ADR-36：历史月最大供货量数据源（插单风险 high 判定）

- 状态：已接受
- 日期：2026-07-22

## 上下文
插单风险 high 判定需「历史月最大供货量」，需确定数据源与口径。

## 决策
- 数据源：金蝶 PUR_PURCHASEORDER + PUR_INSTOCK，二开聚合视图 `V_MATERIAL_SUPPLIER_MONTH_MAX_QTY`（金蝶 BOS 视图，executeBillQuery 可读）
- **落库方式：ETL 同步到 MySQL `supplier_month_max` 表（每日全量），交期路径读 MySQL，不实时打金蝶**（遵循 ADR-31）
- 口径：过去 12 个月，物料 + 供应商维度，**月度入库的最大入库数量**（实际入库才算，只下 PO 未入库不计）
- 视图输出：`FMATERIALID / FSUPPLIERID / FMAX_MONTH_QTY`

### 风险判定
- 询价需求量 > FMAX_MONTH_QTY → `risk_level = high`，标记插单高风险
- 视图查不到该物料 + 供应商历史记录（新供应商 / 新物料）→ `risk_level = medium`，提示【无历史供货记录，请人工评估产能】

## 理由
- 以实际入库口径避免只看订单虚量、高估供应商产能。

## 后果
- ETL 每日全量同步 V_MATERIAL_SUPPLIER_MONTH_MAX_QTY → `supplier_month_max` 表；calc_lead_time 的 risk high 判定读 MySQL。
