# 汽配售后业务智能体（Qipei Agent）

本项目基于我在前司工作期间主导设计的真实业务场景。公司内部代码不便公开，此仓库为我个人整理的脱敏重置版，用于简历作品集的展示，所用文件均为当时开发过程中的决策文档原样保留。

> 面向 B2B 汽配售后工贸工厂的企业级内部业务智能体 —— spec-driven 开发实践
>
> Python 3.11 / FastAPI / 大模型（豆包）/ MySQL 8.0 / Redis / ERP & PIM 集成

[![CI](https://github.com/vina31415/qipei_agent_showcase/actions/workflows/ci.yml/badge.svg)](https://github.com/vina31415/qipei_agent_showcase/actions)


## 30 秒介绍

为汽配工贸工厂的内部员工（业务员 / 跟单 / 仓库 / 售后客服）提供对话式查询：说一句「查 OE 6Q0820803C，客户要 200 件」，一轮对话返回 SKU、适配车型、库存、分级价、交期和插单风险。

**角色：架构设计与技术选型负责人。** 需求分析、全部43 项架构决策（ADR）、决策冻结 spec、可执行计划由我与 dev-Agent 协作产出并由我人工审核确认；编码由独立搭建的 Coding Agent 依据冻结 spec/plan 分里程碑执行，人工在每个里程碑放行。

**量化验收基线**：OE 检索端到端命中率 ≥98%（现状约 70%）｜P95 ≤3s｜规则抽参命中率 ≥95%｜1 轮对话收敛｜交期 / 下单零自动落库。

**规模**：2.3 万 SKU、十万级 OE 映射，日均查询 1900–2400、并发 10–25。

---

## 亮点速览

- **给 LLM 划边界，而不是堆 Agent 框架**：LLM 只做意图识别 / 参数抽取 / 工具选择，规则优先、LLM 兜底（ llm_timeout=2s ，超时降级模板回答）；回答全部确定性模板渲染，价格 / 库存等敏感数据不出内网。
- **权限过滤下沉内网能力层**：敏感字段在能力层（内网）按角色矩阵过滤后才返回，云侧编排层根本接触不到价格与供应商数据。
- **检索不用 RAG**：结构化编码场景用「归一化 + 关系库精确索引」，可解释、可控、不押注模型（[ADR-03](docs/decisions/ADR-03-检索技术选型结构化精确查询.md)）。
- **ERP 实时兜底**：主检索走 MySQL 产品主数据中心（ETL 自金蝶/PIM），miss 时触发金蝶实时兜底并降权标注，兜底耗时计入 P95 口径。
- **43 份 ADR + 决策冻结 spec**：每个决策都有上下文 / 决策 / 理由 / 后果，spec 全文无「待定 / 视情况」类模糊表述（[自检报告](docs/自检报告.md)）。
- **计划可执行、可追溯**：plan 每个步骤含读取文件白名单、验证命令、通过标准、回退方式、commit message，并附 spec↔plan 双向映射表证明「全覆盖、无新增」与风险清单（R1–R4）。

---

## 架构一览

```
        ┌────────────────────────── 云侧（公网区） ──────────────────────────┐
        │  编排层 Orchestrator                                              │
  用户 ──▶  intent → param_extract → tool_dispatch → answer_render         │
        │        （LLM 仅做意图/抽参/工具选择，2s 超时降级模板）               │
        └──────────────┬───────────────────────────────────────────────────┘
                       │ 反向隧道（+ user_id/role，敏感字段已在内网过滤）
        ┌──────────────┴───────────────────────────────────────────────────┐
        │  内网                                                            │
        │  能力层 Capability ──▶ 产品主数据中心（MySQL，ETL 自金蝶/PIM）     │
        │  集成层 Integration ──▶ 金蝶 / PIM（仅 ETL 触发 + 检索 miss 兜底） │
        └──────────────────────────────────────────────────────────────────┘
```

完整架构与数据流：[docs/architecture.md](docs/architecture.md)。设计要点：检索不用 RAG（结构化编码精确匹配）、权限过滤在内网能力层、LLM 不接触价格/库存原文、主路径不实时打 ERP。

## 快速复现（任何人可验证）

```bash
git clone <repo-url> && cd qipei-agent
pip install -e ".[dev]"
ruff check .          # 零告警（spec DoD）
pytest                # 298 个测试全绿，外部依赖全部 mock，无需任何密钥
```

CI（GitHub Actions）在每次 push/PR 自动执行同一套验证：[.github/workflows/ci.yml](.github/workflows/ci.yml)。

## 项目文档导航

| 路径 | 内容 | 建议阅读顺序 |
|---|---|---|
| [docs/architecture.md](docs/architecture.md) | 架构综述、数据流、LLM 边界、决策速查 | **（面试官从这里开始）** |
| [docs/复盘-v1到v2.md](docs/复盘-v1到v2.md) | 第一版交付的失败复盘与 v2 工程化重构 | **（返工故事）** |
| [docs/decisions/](docs/decisions/) | 43 份 ADR，其中 8 份附「作者批注」| 想看决策思维的人 |
| [docs/decisions/archive/](docs/decisions/archive/) | 其余 ADR 原文存档 | 需要完整证据链时 |
| [docs/spec.md](docs/spec.md) | 决策冻结文档（完整输入） | 附录级 |
| [docs/plan.md](docs/plan.md) | 可执行计划：步骤 / 验证命令 / 风险清单 | 附录级 |
| [docs/自检报告.md](docs/自检报告.md) | spec 完备性自检（残余歧义、无理由决策检查） | 附录级 |
| [docs/oe_test_samples.md](docs/oe_test_samples.md) | OE 归一化 26 个测试样本 | 附录级 |
| [docs/brand_normalize.yaml](docs/brand_normalize.yaml) / [customer_level.yaml](docs/customer_level.yaml) | 业务归一化配置示例 | 附录级 |
| `src/qipei_agent/` | 源码（src layout 单包） |
| `tests/` | 298 个测试（镜像 src 结构，全 mock） |

## 开发方法：spec-driven 

本项目本身也是作品的一部分——它展示了一套让 AI 在**严格边界内**交付企业级系统的流程：

1. 与 dev-Agent 讨论收敛架构方案与技术选型落定 → 记录为 43 份 ADR（上下文/决策/理由/后果）；
2. AI 自检完备性 → 我审核 → **spec 冻结**，成为唯一决策源；
3. Plan Agent 把 spec 翻译为可执行 plan（双向映射表证明"全覆盖、无新增"）→ 我审核；
4. Coding Agent 按里程碑执行，每步验证+提交+devlog，**任何 spec 之外的情况停止上报**，由人裁决；
5. 每个里程碑人工放行后继续。

## 关于本仓库

- 业务背景基于真实 B2B 汽配售后场景；外部系统（金蝶/PIM/LLM）在测试中全部 mock，CI 无需任何密钥。
- 未附开源许可证（保留所有权利）：代码仅供浏览与面试验证，如需引用请联系作者。
- spec/plan/ADR 为 AI 协作产出的冻结输入，保留原文呈现完整证据链——这正是本项目的主题。
- 本项目开发过程中使用到的 AI 均为作者本人根据自身开发模式和工作习惯自己组装研发的 Agent ，用于提高我个人的开发效率，未使用目前主流的打包 Harness 开箱即用式 Work Agent ，因其通用性设计无法最大化实现我的 AI 协助开发要求。经本次项目开发验证，由我自研定制版 dev-Agent 的使用产出比原生 AI 的产出成果质量更符合要求，使用成本更可控，且能够在保证交付质量和项目可维护的前提下实现开发过程的提效。
