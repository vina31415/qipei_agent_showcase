# ADR-34：能力层响应 schema 与权限过滤落点

- 状态：已接受
- 日期：2026-07-21

## 上下文
需确定 6 个工具的响应 JSON 结构，并明确权限过滤发生在哪一层、role/user_id 如何传递。

## 决策

### 权限过滤落点
**在能力层（内网）过滤**，非编排层（云侧）。理由：敏感数据（价格/供应商备注/备选交期）不能出内网到云侧编排层（ADR-11/ADR-13）。
- 所有工具请求须携带 `user_id` + `role`（编排层从入口 context 透传）。
- 能力层按 ADR-07 矩阵在返回前过滤字段。

### 统一信封（沿用 ADR-30）
`{request_id, ok, data | error{code,message}}`

### 6 工具响应 schema（data 字段）
```json
// normalize_oe
{ "oe_normalized": "986479012", "is_valid": true }

// search_by_oe
{ "skus": [ { "sku_code": "CP-ENG-00781", "name": "前刹车片", "oe_raw": "0986479012", "oe_type": "原厂", "label": "原厂OE", "image_url": "...", "fitments": [{"brand":"VW","series":"GOLF","model":"GOLF IV","year_start":1997,"year_end":2004}] } ] }

// search_by_fitment
{ "skus": [ { "sku_code": "...", "name": "...", "oe_list": [{"oe_raw":"...","oe_type":"原厂","label":"原厂OE"}], "image_url": "..." } ] }

// get_stock
{ "sku_code": "...", "on_hand": 960 }

// get_price
{ "sku_code": "...", "price": 125.60, "tax_included": true, "original_price": 111.15, "currency": "CNY", "customer_tier": "B", "price_type": "等级价", "qty_range": [51, 200], "note": "" }

// calc_lead_time
{ "sku_code": "...", "lead_time": 12, "supplier_note": "交期取自默认供应商 博世", "risk_level": "none|medium|high", "risk_hint": "", "pos": [{"supplier":"博世","arrival_date":"2026-10-05","qty":500}], "alternatives": [{"supplier":"德尔福","lead_time":15}] }
```

### 字段语义
- `price_type` ∈ `{专属价, 等级价, 人工询价}`
- `qty_range` = `[qty_low, qty_high]`（命中阶梯区间）
- `tax_included` = 是否含税；`original_price` = 未税价（FISINCLUDETAX=false 时保留）
- `currency` = price 表命中行币种（=客户主单币种），get_price 请求**不带 currency**，不做换算

## 理由
- 能力层过滤 → 敏感数据不出内网，符合安全边界。
- 明确字段名 → Plan Agent 可写精确测试断言。

## 后果
- 6 工具请求 body 统一加 `user_id` + `role`（更新 ADR-30）。
- `capability/` 各工具返回结构按此实现；`shared/models.py` 定义 Pydantic 模型。

---

## 作者批注：为什么做这个决策

"权限过滤放哪一层"是这个项目最典型的架构权衡。放编排层（云侧）实现简单，但意味着价格、供应商备注这些敏感字段会先流出内网再被过滤——过滤前的数据已经在公网区内存里了。放能力层（内网）则要求所有工具请求携带 user_id+role，编排层每次调用都要透传身份，麻烦但泄密面最小。我选了后者，并且把它写进接口契约（ADR-30/34）：安全边界靠契约保证，不靠实现自觉。仓库角色查同一 SKU 永远看不到价格，是测试用例里固化死的断言。
