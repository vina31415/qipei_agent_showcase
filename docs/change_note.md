# change_note — spec.md 增量修改（2026-07-24）

依据架构设计 Agent「目标项目默认工程约定」对已冻结 spec.md 做增量更新，新增决策 ADR-39~43，无删除、无既有决策内容变更（ADR-14 目录树被 ADR-42 覆盖修订，属新增决策影响，非独立变更）。

## 新增决策

| 编号 | 决策 | spec 落点 | 一句话说明 |
|---|---|---|---|
| ADR-39 | CI 交付 | §4.4 | DoD 增补可提交 `.github/workflows/ci.yml`（push+PR、Python 3.11、`pip install -e ".[dev]"` → ruff check → pytest、无 secrets、Linux 命令） |
| ADR-40 | 分层 mock 测试策略 | §4.3 | 不可控外部依赖 mock；文件 IO 注入 + tmp_path；外部 API fixture 锁结构 |
| ADR-41 | 依赖注入编码约束 | §3.5 | 外部依赖参数注入、默认绑真实实现；标准库/纯逻辑硬编码 |
| ADR-42 | src layout | §3.3 | apps/ 平铺 → `src/qipei_agent/` 单包 + hatchling（用户拍板） |
| ADR-43 | 依赖版本下限约束 | §3.6 | 补齐 fastapi>=0.110 等主/次版本下限 |

## 修改（非新增决策）

| 位置 | 修改 |
|---|---|
| 文首 | ADR-01~38 → ADR-01~43，并补 ADR-39~43 落点说明 |
| §5 速查表 | DoD 行补 ci.yml；新增「目录结构 / CI / 依赖注入 / mock 策略 / 依赖版本」5 行 |

## 删除

无。
