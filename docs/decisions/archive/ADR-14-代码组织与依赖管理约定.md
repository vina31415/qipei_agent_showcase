# ADR-14：代码组织与依赖管理约定

- 状态：已接受
- 日期：2026-07-16

## 上下文
需确定代码仓库组织方式与依赖管理约定。

## 决策
1. 单一物理主仓（monorepo）；内网 / 云不拆独立实物仓，通过目录 + 部署单元做**逻辑分仓**。
2. 依赖管理采用 `pyproject.toml`（项目从 0 主导开发、无既有约定，取 Python 生态现行标准）。

## 理由
- 单仓：模块少、团队单一，逻辑分仓（`apps/orchestrator` 云侧 vs `capability` / `integration` / `etl` 内网侧）已足够隔离部署边界，拆实物仓徒增协作成本。
- pyproject：版本锁定与依赖声明一体，Coding Agent 可直接用 uv / pip 安装。

## 后果
- 内网侧与云侧代码同仓，靠 `deploy/internal` 与 `deploy/cloud` 两套部署单元区分，构建时各自只打包所需模块。
- 完整目录树落于 spec §3.3。
