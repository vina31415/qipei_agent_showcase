# ADR-26：价格取数与业务口径（修正 ADR-19）

- 状态：已接受
- 日期：2026-07-20

## 上下文
需确定分级价的取数链路与业务口径（客户等级来源、数量阶梯、币种、含税），使 get_price 可正确实现。

## 决策

### 修正 ADR-19 的字段
- 价格本 FormId 以 **SAL_PRICEBASE** 为准（原 ADR-19 记 BD_PriceBase）。
- 数量区间字段为 **FQTYLOW / FQTYHIGH**（原记 FQTYMIN / FQTYMAX）。
- 客户等级字段为 **FCUSTLEVELID**（关联基础资料 BD_CUSTLEVEL 取 FNAME）。

### 客户等级 customer_tier 来源
1. 客户主单 BD_CUSTOMER.FCUSTLEVELID（内码）
2. 关联 BD_CUSTLEVEL 取等级名称 FNAME
3. 经 `customer_level.yaml` 映射为标准编码 customer_tier（A/B/C/D 四级）
- 等级是静态主数据，不随单次订单变更；查价时先拿客户 ID → 取 customer_tier → 匹配分级价本。

### 数量阶梯价
- SAL_PRICEBASE 阶梯为数量区间定价：按 SKU + 客户等级 + 询价数量 quantity，匹配 FQTYLOW ~ FQTYHIGH 区间取单价。
- 询价数量超出所有阶梯上限 → 取最大阶梯价，并提示【超阶梯，需人工议价】。
- 示例阶梯：1-50 / 51-200 / 201-1000 / 1000 以上。

### 币种
- FCURRENCYID 关联 BD_CURRENCY 取编码（CNY / USD / EUR）；国内连锁默认 CNY，海外进口商默认 USD。
- 不做汇率换算，仅展示价格本原始币种；汇率换算后置单独模块。
- **币种优先级**：价格币种以 price 表命中行的 `currency` 为准（= 客户主单币种）；入口 context 的 `currency` 仅展示偏好，若与 price.currency 不一致仍展示 price.currency（不做换算）；多币种行按客户主单币种过滤。

### 含税 / 未税
- SAL_PRICEBASE.FISINCLUDETAX：true=含税，false=未税。
- 对外报价统一展示含税价；未税价用 FTAXRATE 自动计算含税展示值，同时保留原始未税价返回业务员。

### 价格命中优先级
SAL_PRICEBASE 同时存在两套价：客户专属价（FCUSTID 维度）+ 客户等级价（FCUSTLEVELID 维度）。
优先级：**客户专属价 > 客户等级价 > 无预设价格（标记需业务员手动询价）**。
1. 有【FCUSTID + 物料】专属价 → 取客户专属价（少数海外头部进口商单独维护协议价）
2. 无专属价 → 匹配该客户等级 FCUSTLEVELID 的等级阶梯价
3. 两者都无 → 无预设价格，标记需业务员手动询价

## 理由
- 分级价落地需客户等级、数量阶梯、币种、含税四要素，缺一无法正确取数。
- 对外统一含税、保留未税，兼顾客户展示与业务员内部核算。

## 后果
- get_price 需扩展入参（customer_id、quantity、currency、含税口径），见能力层契约 ADR。
- price 表数据模型覆盖 FCUSTLEVELID / FQTYLOW / FQTYHIGH / FISINCLUDETAX / FTAXRATE / FCURRENCYID。
- `customer_level.yaml` 与 `brand_normalize.yaml` 作为配置数据随 spec 交付。
