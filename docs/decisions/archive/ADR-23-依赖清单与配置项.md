# ADR-23：依赖清单与配置项（含默认值）

- 状态：已接受
- 日期：2026-07-17

## 上下文
需确定依赖清单、环境变量与业务配置默认值，供 Coding Agent 直接引用。

## 决策

### 依赖（pyproject，版本在 pyproject 锁定、开发时取当前稳定版）
`fastapi` / `uvicorn` / `pydantic(v2)` / `httpx` / `sqlalchemy(2.x)` / `pymysql` / `volcengine`(豆包 SDK) / `pydantic-settings` / `pytest` / `ruff`

### 环境变量（必填，无默认值）
`KINGDEE_BASE_URL` / `KINGDEE_TOKEN` / `PIM_BASE_URL` / `PIM_ACCESS_TOKEN` / `DOUBAO_API_KEY` / `DOUBAO_MODEL` / `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB`

### 业务配置 config/*.yaml（含默认值）
| 配置项 | 默认值 |
|---|---|
| 现货交期 | 1 天 |
| 采购周期兜底 | 15 天 |
| OE 前缀清单 | 8 项（ADR-15） |
| 纯数字去前导零 | 开 |
| 宽松匹配开关 | 默认关 |
| brand 映射 | 见 ADR-21 |
| connect_timeout / read_timeout | 5s / 10s |
| max_retries | 3 |
| 429 退避 | 读 Retry-After，无则 5s |
| backoff_initial / factor / max | 1s / ×2 / 30s |
| sync_concurrency | 5 |
| llm_timeout | 2s |

## 理由
- 环境变量承载敏感凭证；业务参数落 yaml 便于运维调整，均需在 spec §5 汇总。

## 后果
- 配置加载统一 pydantic-settings；默认值在 spec §5 显式写出，下游不得编造。
