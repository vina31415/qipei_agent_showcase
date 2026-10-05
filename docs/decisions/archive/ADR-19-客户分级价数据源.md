# ADR-19：客户分级价数据源（BD_PriceBase）

- 状态：已接受
- 日期：2026-07-17

## 上下文
分级价（按客户等级）不来自物料主数据 BD_MATERIAL，来自独立销售价格本。业务方 IT 提供契约如下。

## 决策
1. 客户分级价取独立销售价格本 `BD_PriceBase`（executeBillQuery，FormId=BD_PriceBase）。
2. FieldKeys：`FID,FBillNo,FCUSTID,FCUSTLEVEL,FMATERIALID,FPRICE,FQTYMIN,FQTYMAX,FCURRENCYID,FVALIDDATE,FINVALIDDATE,FISACTIVATE`
3. 客户等级字段 = `FCUSTLEVEL`（返回等级编码）。
4. 等级编码→名称翻译：本地配置 `customer_level.yaml`（如 A类大客户/B连锁/C普通经销商），不实时查 BD_Customer。
5. 查询过滤（只取有效价）：`FISACTIVATE=1 AND FVALIDDATE<=当前日期 AND FINVALIDDATE>=当前日期`
6. 降级：该客户+物料在价格本无匹配记录时，读物料主数据标准价 BD_MATERIAL.FPRICE。
7. 权限：销售价格本只读，禁止写。
8. 鉴权：同金蝶统一鉴权 `Authorization: KDSpaceToken {金蝶星空token}`（ADR-16）。

## 理由
- 分级价带客户等级 + 起订量阶梯 + 有效期三维度，物料主数据 FPRICE 只是基准价，不满足分级需求。
- 等级名称翻译用本地配置，省一次金蝶调用、降低限流压力。

## 后果
- price 表数据源改为 BD_PriceBase；金蝶适配器新增 BD_PriceBase 查询封装 + 有效期/启用过滤。
- 价格命中流程：先查 BD_PriceBase（客户+物料+等级+有效期），miss 降级 BD_MATERIAL.FPRICE。
