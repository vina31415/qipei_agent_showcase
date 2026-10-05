# ADR-10：技术栈选型

- 状态：已接受
- 日期：2026-07-15

## 上下文
需为 Coding Agent 确定可执行的技术栈（语言 / 框架 / SDK / 编排 / ETL / 存储，含版本约束）。

## 决策
| 项 | 选型 | 版本约束 |
|---|---|---|
| 语言 | Python | 3.11 |
| Web 框架 | FastAPI | 最新稳定版 |
| LLM SDK | 豆包官方 SDK（火山方舟） | 最新稳定版 |
| 编排 | 自研轻量编排（规则优先 + 模型兜底） | — |
| ETL | Python 脚本 + 定时任务 | — |
| 存储 | MySQL | 8.0 |

## 理由
- Python 3.11：团队既定 Python 栈；异步 + AI 生态成熟，FastAPI / Pydantic v2 兼容好。
- FastAPI：异步、Pydantic 原生校验、自动 OpenAPI，能力层工具天然以 API 形态暴露，跨云 / 内网调用统一走 HTTP。
- 豆包 SDK：ADR-08 已定豆包，官方 SDK 支持 function calling，编排层对 LLM 做接口抽象可替换。
- 自研轻量编排：工具仅 6 个、需「规则优先、模型兜底」的强可控控制流，直连豆包 function calling 的循环仅百行级，透明可调试；LangChain 抽象过重、版本迭代快，M1 无收益。
- ETL 脚本：十万行级定时同步，无需 Airflow 级调度。
- MySQL 8.0：ADR-08 已定，B-Tree 索引足够。

## 后果
- 编排层引入豆包 function calling 循环，需自测意图 / 参数抽取的规则命中率。
- 未来若扩展复杂多步工作流（如报价审批流），再评估 LangGraph（另立 ADR）。
