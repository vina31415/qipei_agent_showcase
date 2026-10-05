# ADR-39 CI 交付（默认工程约定）

日期：2026-07-24

## 决定
目标项目 DoD（spec §4.4）须包含可提交的 `.github/workflows/ci.yml`：触发 push + PR；Python 单版本 = 3.11（spec §3.1 锁定版本）；步骤 `pip install -e ".[dev]"` → `ruff check` → `pytest`；无 secrets（不引用 `${{ secrets.XXX }}`）；Linux 标准命令（不照搬本地 `.venv/Scripts/...` 路径）。

## 理由
保证项目可直接跑 CI、可复现；单版本锁定降低矩阵复杂度；无 secrets 保证可公开提交；Linux 命令保证 CI 环境可移植。

## 影响与代价
- pyproject.toml 需含 `[project.optional-dependencies] dev = ["pytest", "ruff"]` 以支持 `pip install -e ".[dev]"`。
- 开发须保证 `ruff check` 与 `pytest` 在干净 Linux 环境可过。
