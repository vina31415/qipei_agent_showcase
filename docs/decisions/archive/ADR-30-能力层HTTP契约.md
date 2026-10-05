# ADR-30：能力层 HTTP 契约

- 状态：已接受
- 日期：2026-07-21

## 上下文
能力层（内网侧 FastAPI）经安全通道（ADR-12）被编排层调用，需定义 6 个工具的服务间 HTTP 契约。

## 决策

### 统一约定
- 端点：`POST /api/v1/tools/{tool_name}`
- 请求头：`X-Request-Id`（编排层生成，贯穿全链路，回显在响应）
- 鉴权：能力层在内网网关侧，编排层经安全通道调用，能力层信任网关已鉴权（可选加内部 service token）
- 超时/重试归属：编排层负责调用超时/重试（能力层工具是同步幂等查询）；能力层内部对金蝶/PIM 的调用按 ADR-22 参数重试

### 统一响应信封
- 成功：`{ "request_id": "...", "ok": true, "data": {...} }`
- 失败：`{ "request_id": "...", "ok": false, "error": { "code": "E_XXX", "message": "..." } }`

### 6 个工具端点
| 工具 | 端点 | 请求 body | data 响应 |
|---|---|---|---|
| normalize_oe | `/tools/normalize_oe` | `{oe_raw}` | `{oe_normalized}` |
| search_by_oe | `/tools/search_by_oe` | `{oe_normalized, loose}` | `{skus:[...]}` |
| search_by_fitment | `/tools/search_by_fitment` | `{brand, series, model, year}` | `{skus:[...]}` |
| get_stock | `/tools/get_stock` | `{sku_code}` | `{on_hand}` |
| get_price | `/tools/get_price` | `{sku_code, customer_id, quantity}` | `{price, tax_included, original_price, currency, customer_tier, price_type, qty_range}` |
| calc_lead_time | `/tools/calc_lead_time` | `{sku_code, quantity}` | `{lead_time, supplier_note, risk_level, pos:[...], ...}` |

### get_price 入参说明
- 入参含 `customer_id`（而非 customer_tier）：customer_tier 由能力层内部经 BD_CUSTOMER → customer_level.yaml 派生，不信任调用方传 tier（ADR-26）。

## 理由
- 统一信封 + 统一错误码，编排层按 `ok`/`error` 判断，简化调用方处理。
- customer_id 为权威入参，tier 派生在能力层，避免调用方传错等级导致错价。

## 后果
- `capability/main.py` 暴露 6 个工具端点，共享统一信封与错误码。
- 编排层 `tool_dispatch.py` 按此契约调用能力层。
