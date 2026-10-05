# ADR-22：错误处理与日志约定

- 状态：已接受
- 日期：2026-07-17

## 上下文
需统一错误处理与日志约定，保证全链路可观测与关键操作可审计，并为集成层提供可引用的重试/超时参数。

## 决策

### 日志
- 结构化 JSON，每条带 `request_id`（trace id）贯穿 渠道→编排→能力→集成 全链路。
- 埋点：检索命中/未命中、工具耗时、金蝶/PIM 调用失败、LLM 意图/抽参结果。

### 错误处理
| 层 | 策略 |
|---|---|
| 集成层 | 金蝶/PIM 失败 → 按下方参数表重试（指数退避，429 必退避），最终失败返回统一错误码 + 降级 |
| 能力层 | 工具返回结构化结果（含 `error` 字段），不抛裸异常 |
| 编排层 | LLM 超时/失败 → 降级规则抽取 + 模板回答 |
| 检索兜底 | 主检索 miss → ERP 兜底检索（ADR-04） |

### 集成重试与超时参数（默认值，落 app.yaml）
| 参数 | 默认值 | 说明 |
|---|---|---|
| connect_timeout | 5s | 建连超时 |
| read_timeout | 10s | 单次查询响应超时 |
| max_retries | 3 | 超时/网络错/5xx 重试上限 |
| 429 退避 | 读 Retry-After，无则 5s 起步 | 限流必退避 |
| backoff_initial | 1s | 首次重试前等待 |
| backoff_factor | 2 | 指数退避 1s→2s→4s |
| backoff_max | 30s | 退避封顶 |
| sync_concurrency | 5 | ETL 同步节流并发（金蝶硬上限 10，留余量） |
| llm_timeout | 2s | 编排层 LLM 调用超时（ADR-31，超时降级模板回答） |

> PIM 集成参数与金蝶对称（connect 5s / read 10s / retries 3 / backoff 1s×2 封顶 30s）。

### 统一错误码
`E_KINGDEE_TIMEOUT` / `E_PIM_UNAVAILABLE` / `E_NOT_FOUND` / `E_LLM_FAILED` / `E_RATE_LIMIT`

## 理由
- request_id 贯穿全链路，支撑 spec §4.2 可观测/审计目标。
- 分层降级保证单点故障不整链崩溃。

## 后果
- 全模块统一日志工具与错误码常量，落 `shared/`。
- 审计日志（查询、交期计算）留痕，满足 spec §4.2。
