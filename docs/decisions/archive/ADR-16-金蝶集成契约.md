# ADR-16：金蝶集成契约（executeBillQuery）

- 状态：已接受
- 日期：2026-07-16

## 上下文
金蝶云星空 ERP 提供只读动态单据查询。需确定集成层 kingdee.py 的精确调用契约。鉴权口径经业务方 IT 澄清：金蝶与自研 PIM 为两套独立鉴权，金蝶统一走 KDSpaceToken。

## 决策

### 调用契约
- 地址：`https://erp-gateway.xxx-auto.com/k3cloudapi/Kingdee.BOS.WebApi.ServicesStub.DynamicFormService.ExecuteBillQuery`
- 方法：POST，`Content-Type: application/json`
- 入参：`{FormId, FieldKeys, FilterString, OrderString, TopRowCount, StartRow, Limit}`
  - FormId = `BD_MATERIAL`
  - FieldKeys = `FMATERIALID,FMATERIALNUMBER,FNAME,FSTOCKQTY,FAVAILABLEQTY,FPRICE,FTAXRATE,FCUSTPRICE`
- 返回：`Result.IsSuccess` / `Result.Rows`（二维数组）/ `Result.TotalCount`

### 鉴权（金蝶云星空 ERP，含 BD_PriceBase / PO / 物料 / 客户档案等全部金蝶接口）
- 标准鉴权头：`Authorization: KDSpaceToken {金蝶星空token}`
- 金蝶星空 token 经金蝶登录接口获取（token 获取步骤与有效期待 IT 最终确认）

### 限制与权限
- 同一 AppKey 并发 ≤ 10 条 executeBillQuery，超限返回 429
- 权限只读：库存单据、物料(SKU)、价格本、客户价表；**禁止写**

## 理由
- 金蝶与 PIM 为两套独立鉴权体系，金蝶统一用 KDSpaceToken（PIM 用 Bearer，见 ADR-20）。
- 只读权限与 ADR-06「不自动写」红线一致。

## 后果
- kingdee.py 实现「获取金蝶星空 token → 带 KDSpaceToken 查询」，处理 429 限流（重试/退避）与 token 过期刷新。
- ETL 同步金蝶库存/价格时受 10 并发上限约束（串行/节流），检索主路径读产品主数据中心（MySQL），不逐次打金蝶。
- 现货字段 FSTOCKQTY（库存量）与 FAVAILABLEQTY（可用量）并存，「现货判断」默认取 FAVAILABLEQTY（可用量）。
