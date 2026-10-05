# ADR-42 目录结构 src layout

日期：2026-07-24

## 背景
原 ADR-14 采用 `apps/{orchestrator,capability,integration}` + `etl` + `shared` 的平铺多服务结构。提示词默认工程约定要求 `src/<package_name>/` + hatchling 构建后端、tests 镜像 src。两者互斥，需重新定夺。

## 候选方案对比

| 方案 | 适用性 | 复杂度 | 可维护性 | 生态与风险 |
|---|---|---|---|---|
| A. apps/ 平铺多服务（原 ADR-14） | 贴合云/内网分侧部署 | 低（无包结构） | 中（模块边界靠约定） | hatchling 打包需额外配置，导入路径不稳定 |
| B. src/qipei_agent/ 单包 + hatchling（选中） | 标准 src layout，IDE/工具链友好 | 中（需迁移导入路径） | 高（明确命名空间） | 业界标准，低风险 |

## 决定
采用 src layout：业务代码 `src/qipei_agent/`（包名 = project_name `qipei-agent` 连字符转下划线），tests 镜像 src，构建后端 hatchling。`config/` 保留顶层（部署期配置不入包）。多服务通过 `qipei_agent.orchestrator` / `qipei_agent.capability` / `qipei_agent.integration` 子包区分，仍可分别部署。

## 理由
用户拍板改为 src 单包结构；src layout 为 Python 打包业界标准，导入路径稳定、IDE/工具链零配置，便于 CI 与发布；用子包替代原 apps/ 分侧，保留云/内网分侧部署能力。

## 影响与代价
- 修订 ADR-14 目录树；所有 import 从 `apps.*` / 顶层模块迁移到 `qipei_agent.*`。
- pyproject.toml 改用 hatchling + `[tool.hatch.build.targets.wheel] packages = ["src/qipei_agent"]`。
- `config/` yaml 不入包，运行时经环境变量/绝对路径加载。
