# ADR-28：ERP 兜底检索契约（细化 ADR-04）

- 状态：已接受
- 日期：2026-07-20

## 上下文
需确定主检索 miss 时 ERP 兜底查询的具体对象与字段，支撑 98% 端到端命中率验收。

## 决策
主接口异常/未命中时，降级兜底查询金蝶（只读，共用 executeBillQuery + KDSpaceToken），单次 limit=20：

| 业务对象 | FormId | 核心查询字段 |
|---|---|---|
| 物料主数据 | BD_MATERIAL | FMATERIALID, FNAME, FNUMBER, FLEADTIME |
| 客户主数据 | BD_CUSTOMER | FCUSTID, FNUMBER, FNAME, FCUSTLEVELID, FCURRENCYID |
| 物料供应商关联 | BD_MATERIALSUPPLIER | FMATERIALID, FSUPPLIERID, FISDEFAULTSUPPLIER, FLEADTIMESUPP |
| 采购订单（在途） | PUR_PURCHASEORDER | FID, FBillNo, FMATERIALID, FPLANARRIVALDATE, FQTY, FRECEIVEQTY, FDOCUMENTSTATUS |
| 销售价格本 | SAL_PRICEBASE | FMATERIALID, FCUSTLEVELID, FQTYLOW, FQTYHIGH, FPRICE, FISINCLUDETAX, FTAXRATE, FCURRENCYID |

## 理由
- 兜底查询只读 + 限流，与主接口共用 executeBillQuery，避免额外集成面。

## 后果
- 兜底结果需与主检索结果合并、排序、标注「兜底来源」；兜底耗时计入 P95 ≤3s 预算。
- 集成层 kingdee.py 需封装上述 5 个 Form 的兜底查询。
