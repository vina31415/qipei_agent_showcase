# 汽配售后业务智能体 执行计划（plan.md）

## 1. 概述

**项目一句话目标**：为 B2B 汽配售后工贸工厂打造内部业务智能体，M1 实现「对话式 OE 号查询 + 车型查询 + 库存/分级价/交期」，1 轮对话收敛，端到端 P95≤3s，交期/下单零自动落库。

**spec.md 引用**：`spec.md`（决策冻结文档，用户已审核确认，无未确认项）+ 附件 ADR-01~43.md + `config/*.yaml` + `oe_test_samples.md`（26 样本）构成完整冻结输入。本 plan.md 仅翻译上述决策，不引入任何 spec 之外的内容。

> 说明：本 plan.md 由 v1（ADR-01~38）经 **spec v2 增量更新**而来（非全量重规划）。llm_timeout 取 spec 冻结值 **2s**（spec §3.6/§5、ADR-23、ADR-31 决策正文一致——见风险清单 R3）。

---

## 0. 本版 spec 变更说明（增量更新）

> 用户要求：在原 plan 基础上更新，不推翻重规划、不使 Coding Agent 全量重来。以下为 spec v1→v2 变更要点与路径迁移映射（Coding Agent 迁移既有代码的参照）。

| spec 变更 | 出处 | 对 plan 的改动 |
|---|---|---|
| 目录结构 flat（apps//etl//shared/ 根级）→ src layout 单包 `qipei_agent` | §3.3、ADR-42 | 全部步骤源码路径机械迁移；tests 镜像 src/qipei_agent/；config 不入包；P1-1 重写 |
| 依赖加版本下限 + hatchling 构建后端 + dev 可选依赖 | §3.6、ADR-43、ADR-42 | P1-1 |
| DoD 增「交付可提交 `.github/workflows/ci.yml`」+ CI 约定 | §4.4、ADR-39 | P1-1（建 ci.yml）、P5-10（DoD） |
| 依赖注入编码约束 | §3.5、ADR-41 | 全局执行约定 + 各网络/LLM/文件 IO 步骤 |
| 分层 mock 策略 | §4.3、ADR-40 | 全局执行约定 + P5-* 测试步骤 |

**路径迁移映射（机械，不重写业务逻辑）**：
- 源码：`qipei-agent/apps/` → `qipei-agent/src/qipei_agent/`；`qipei-agent/etl/` → `qipei-agent/src/qipei_agent/etl/`；`qipei-agent/shared/` → `qipei-agent/src/qipei_agent/shared/`。
- 包导入：`from shared.xxx` → `from qipei_agent.shared.xxx`（src layout 下包名 = `qipei_agent`，= project_name `qipei-agent` 连字符转下划线）。
- 测试镜像：`qipei-agent/tests/test_*.py` 按被测包落位到 `tests/{capability,orchestrator,integration,etl,shared}/`（spec §3.3「tests 镜像 src/qipei_agent/」）。
- DDL 工件：`schema.sql` 移出包，落 `qipei-agent/deploy/schema.sql`（部署初始化，不入包）。
- 不变：`qipei-agent/config/`（部署期配置，不入包）、`qipei-agent/deploy/`。
- Coding Agent：对已写代码按上述映射机械迁移 + 调整 import，**不重写业务逻辑**；迁移后按对应步骤验证命令复核。

> 说明：spec §3.3 目录树为高层结构（列每包核心模块）。以下辅助模块亦由 spec 决策导出、非新增：`orchestrator/session.py`+`audit.py`（ADR-33 会话 / ADR-32 审计）、`capability/envelope.py`（ADR-30 统一信封）、`capability/permission_filter.py`（ADR-07 权限落点）、`capability/normalize_oe.py`（§3.5 normalize_oe 工具）、`shared/errors.py`+`request_id.py`（§3.7 错误码/request_id）。

---

## 2. spec 决策映射表

> 证明「全覆盖、无新增」：spec 每条决策均有 plan 步骤承接；每个步骤均能追溯到 spec 出处。

| spec.md 决策（章节/ADR） | 对应 plan 步骤 |
|---|---|
| §3.3 目录结构（ADR-14、ADR-42 src layout 单包 + hatchling + tests 镜像 + config 不入包） | P1-1 |
| §3.6 依赖清单 + 版本下限（ADR-23、ADR-43） | P1-1 |
| §3.6 环境变量（必填，无默认值） | P1-1、P1-3 |
| §3.6 业务配置默认值 + config/*.yaml（ADR-15/21/23/26/07） | P1-2 |
| §3.5 依赖注入编码约束（ADR-41） | 全局执行约定；渗透 P2-2/P2-3/P2-4/P3-3/P3-4/P4-1/P4-2/P4-3/P4-4 |
| §3.5 错误码 E_* + 结构化日志 request_id（ADR-22） | P1-3 |
| §3.5 能力层统一信封 + X-Request-Id + 6 工具契约（ADR-30/34） | P3-1 |
| §3.5 权限矩阵过滤在能力层（ADR-07） | P3-8（渗透 P3-2~P3-7） |
| §3.5 OE 归一化规则（ADR-15 v3 流水线+前缀+两模式+多SKU排序） | P1-2、P3-2、P5-1 |
| §3.4 数据模型 10 表（ADR-04/15/20/21/26/27/32/36） | P2-1 |
| §3.5 集成层-金蝶 executeBillQuery + 鉴权 + 并发/429（ADR-16/29） | P2-2、P5-7 |
| §3.5 集成层-PIM oe-vehicle + 鉴权刷新（ADR-20/29） | P2-3、P5-7 |
| §3.5 ERP 兜底 5 表单 + OE 兜底 BD_MATERIAL_OE_EXT（ADR-28/35） | P2-2、P3-3、P5-3 |
| §3.4/§3.5 ETL 同步频率 + 幂等 + 失败重试 + 审计存储（ADR-32） | P2-4、P4-1（审计写入）、P5-10 |
| §3.5 search_by_oe 契约 + 兜底（ADR-34/35） | P3-3、P5-3 |
| §3.5 search_by_fitment 契约（ADR-21/34） | P3-4、P5-3 |
| §3.5 get_stock 契约 + FAVAILABLEQTY（ADR-17/34） | P3-5、P5-3 |
| §3.5 价格取数 优先级/阶梯/含税/币种（ADR-26/34） | P3-6、P5-5 |
| §3.5 交期规则 三分支/拆分/供应商/risk（ADR-17/27/37） | P3-7、P5-4 |
| §3.5 入口契约 POST /api/v1/chat + Redis 会话（ADR-25/33） | P4-1 |
| §3.5 编排规则 4 意图 + 规则优先抽参 + 豆包兜底 + 追问 + 工具顺序 + 模板（ADR-33/31） | P4-2、P4-3、P4-4、P4-5、P5-8 |
| §4.3 规则命中率判定 + 意图/抽参测试集（ADR-38） | P5-9 |
| §4.3 分层 mock 策略（ADR-40） | 全局执行约定；P5-1~P5-8、P5-9（测试落点） |
| §4.1/§4.3 功能验收 + 必测场景（ADR-24） | P5-1~P5-8、P5-10 |
| §4.4 DoD：代码 + pytest 全绿(≥80%) + ruff 无告警 + 审计留痕 + 可提交 ci.yml（ADR-39） | P5-10 |
| §4.4 CI 约定 + .github/workflows/ci.yml（ADR-39） | P1-1（建 ci.yml）、P5-10（复核） |
| §6 红线：零写操作 / 敏感数据不出网 / 不对仓库开放（ADR-06/13/07） | P3-8、P5-6、P5-10（全链路约束） |

---

## 3. 里程碑与步骤

### 里程碑 M1：项目骨架与配置

#### 步骤 P1-1：搭建 src 布局骨架、依赖清单与 CI
- **目标**：按 ADR-42 建立 src layout 单包骨架（qipei_agent），锁定 spec §3.6 依赖（版本下限，ADR-43）与 hatchling 构建，交付 `.github/workflows/ci.yml`（ADR-39）。
- **读取文件**：`spec.md`（§3.3、§3.6、§4.4）、`ADR-42.md`、`ADR-43.md`、`ADR-39.md`、`ADR-23.md`、附件 `oe_test_samples.md`。
- **修改/新建文件**：`qipei-agent/pyproject.toml`、`qipei-agent/.gitignore`、`qipei-agent/README.md`、`qipei-agent/.github/workflows/ci.yml`、`qipei-agent/src/qipei_agent/__init__.py`、`qipei-agent/src/qipei_agent/orchestrator/__init__.py`、`qipei-agent/src/qipei_agent/capability/__init__.py`、`qipei-agent/src/qipei_agent/integration/__init__.py`、`qipei-agent/src/qipei_agent/etl/__init__.py`、`qipei-agent/src/qipei_agent/shared/__init__.py`、`qipei-agent/config/`、`qipei-agent/tests/oe_test_samples.md`（放置附件样本）、`qipei-agent/deploy/internal/`、`qipei-agent/deploy/cloud/`。
- **数据契约**：输入 spec §3.3 目录树（src layout + tests 镜像）+ §3.6 依赖版本下限 + §4.4 CI 约定；输出 pyproject.toml（hatchling + [project.optional-dependencies] dev=pytest/ruff + 依赖版本下限）+ ci.yml。
- **依赖**：spec §3.3、§3.6、§4.4；ADR-42、ADR-43、ADR-39、ADR-23。
- **实现要点**：① 目录树严格按 spec §3.3：`src/qipei_agent/{orchestrator,capability,integration,etl,shared}` + `config`（部署期配置，不入包）+ `tests`（镜像 src/qipei_agent/，即 tests/{orchestrator,capability,integration,etl,shared}/，含 oe_test_samples）+ `deploy/{internal,cloud}` + `.github/workflows/ci.yml`；② pyproject：hatchling 构建后端、包名 `qipei_agent`（= project_name `qipei-agent` 连字符转下划线）、依赖逐项照抄 spec §3.6 版本下限（fastapi>=0.110 / uvicorn>=0.29 / pydantic>=2.6,<3 / httpx>=0.27 / sqlalchemy>=2.0,<3 / pymysql>=1.1 / volcengine>=1.0 / pydantic-settings>=2.2 / redis>=5.0 / pytest>=8.0 / ruff>=0.4），不增删；③ [project.optional-dependencies] dev = pytest/ruff；④ ci.yml 照 ADR-39：push+PR 触发、Python 3.11、`pip install -e ".[dev]"` → `ruff check` → `pytest`、无 secrets、Linux 标准命令（不照搬本地 `.venv/Scripts/...` 路径）；⑤ 环境变量列入文档/配置加载说明，但**不写默认值**（ADR-23 全部必填无默认）；⑥ 各包建 `__init__.py` 占位，不写业务代码。
- **验证命令**：`cd qipei-agent && pip install -e ".[dev]" && python -c "import qipei_agent, fastapi, httpx, sqlalchemy, pymysql, redis; print('ok')" && pytest --version && ruff --version`
- **通过标准**：安装无报错，`import qipei_agent` 与外部依赖导入成功输出 `ok`，pytest/ruff 版本可打印。
- **人工确认点**：`cat qipei-agent/pyproject.toml` 确认依赖版本下限与 spec §3.6 完全一致（无多无少）、构建后端为 hatchling、dev 依赖=pytest/ruff；`cat .github/workflows/ci.yml` 确认 push+PR 触发、Python 3.11、`pip install -e ".[dev]"` → `ruff check` → `pytest`、无 secrets、Linux 命令。
- **回退方式**：`rm -rf qipei-agent/` 重建（本步前无 commit，直接清理重做）。
- **commit message**：`feat(plan-P1-1): src 布局骨架与依赖与 CI`

#### 步骤 P1-2：编写 config/*.yaml 配置文件
- **目标**：落 spec 要求的全部业务配置文件（规则数据 + 默认值；部署期配置，不入包）。
- **读取文件**：`spec.md`（§3.3、§3.4、§3.5、§3.6）、`ADR-15.md`、`ADR-21.md`、`ADR-23.md`、`ADR-26.md`、`ADR-07.md`、附件 `brand_normalize.yaml`、`customer_level.yaml`。
- **修改/新建文件**：`qipei-agent/config/oe_normalize.yaml`、`qipei-agent/config/brand_normalize.yaml`、`qipei-agent/config/customer_level.yaml`、`qipei-agent/config/permission.yaml`、`qipei-agent/config/app.yaml`。
- **数据契约**：输入 spec §3.6 默认值表 + ADR-15 前缀清单/分隔符/去前导零/无效规则 + 附件 brand/customer 映射；输出 5 个 yaml（键值与附件逐字一致）。
- **依赖**：spec §3.3、§3.6；ADR-15、ADR-21、ADR-23、ADR-26、ADR-07。
- **实现要点**：① `oe_normalize.yaml`：前缀清单 8 项（大写，长度降序+边界规则说明）、分隔符集合、去前导零=开、宽松匹配=关、全0 无效标记（规则落配置不硬编码，ADR-15）；② `brand_normalize.yaml`、`customer_level.yaml`：**逐字照抄附件**（key=原始录入值/value=标准编码，含兜底）；③ `permission.yaml`：按 ADR-07 矩阵落角色×字段可见性（业务员/跟单全量；售后隐藏供应商备注+备选供应商交期；仓库仅库存/SKU/品名/库位/图片/车型适配，隐藏所有交期/价格/供应商备注/客户等级）；④ `app.yaml`：spec §3.6 默认值（现货交期1天/采购兜底15天/宽松关/去前导零开/connect5s/read10s/max_retries3/429读Retry-After无则5s/backoff1s×2封顶30s/sync_concurrency5/llm_timeout2s）。
- **验证命令**：`cd qipei-agent && python -c "import yaml,sys; [yaml.safe_load(open(f'config/{n}.yaml',encoding='utf-8')) for n in ['oe_normalize','brand_normalize','customer_level','permission','app']]; print('yaml-ok')"`
- **通过标准**：5 个文件均 YAML 合法可解析，输出 `yaml-ok`。
- **人工确认点**：`diff` 确认 `brand_normalize.yaml`/`customer_level.yaml` 与附件逐字一致；`cat config/app.yaml` 确认默认值与 spec §3.6 逐项对应（尤其 llm_timeout=2s）。
- **回退方式**：`git checkout -- qipei-agent/config/`（回到 P1-1 后状态）。
- **commit message**：`feat(plan-P1-2): config/*.yaml 配置文件`

#### 步骤 P1-3：搭建 shared 基础设施（模型/配置/权限/错误/请求ID）
- **目标**：实现跨包复用的 shared 层（配置加载、Pydantic 模型、权限过滤、错误码、request_id 工具、brand/客户等级映射纯函数）。
- **读取文件**：`spec.md`（§3.4、§3.5、§3.6）、`ADR-22.md`、`ADR-23.md`、`ADR-34.md`、`ADR-07.md`、`qipei-agent/config/*.yaml`（P1-2 产出）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/shared/config.py`、`qipei-agent/src/qipei_agent/shared/models.py`、`qipei-agent/src/qipei_agent/shared/permissions.py`、`qipei-agent/src/qipei_agent/shared/errors.py`、`qipei-agent/src/qipei_agent/shared/request_id.py`。
- **数据契约**：输入 spec §3.6 环境变量/默认值 + §3.5 错误码 + §3.4 表字段 + ADR-34 响应 schema；输出可被各包 import 的 shared 模块。
- **依赖**：spec §3.4、§3.5、§3.6；ADR-22、ADR-23、ADR-34、ADR-07；步骤 P1-1、P1-2。
- **实现要点**：① `config.py`：pydantic-settings 加载环境变量（KINGDEE_*/PIM_*/DOUBAO_*/MYSQL_*/REDIS_URL，无默认）+ 读取 config/*.yaml 注入业务默认值（config/*.yaml 为部署期配置、不入包，运行时由部署侧提供路径加载；不新增 spec 外环境变量）；② `models.py`：按 ADR-34 的 6 工具响应 schema 定义 Pydantic 模型（统一信封 Envelope{request_id,ok,data|error} + 各工具 data 模型）；③ `errors.py`：spec §3.5 五错误码常量 + 结构化 JSON 日志（request_id 贯穿）；④ `request_id.py`：request_id 生成/透传工具；⑤ `permissions.py`：按 ADR-07 矩阵实现字段过滤函数（输入 role+原始字段集→过滤后字段集，供能力层调用）；⑥ brand/客户等级映射（读 brand_normalize.yaml/customer_level.yaml）作为 shared 纯函数提供，供能力层/ETL/编排层复用。仅写策略层，不写业务逻辑。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/shared/ && python -c "from qipei_agent.shared.config import settings; from qipei_agent.shared.errors import E_NOT_FOUND; from qipei_agent.shared.permissions import filter_fields; print('shared-ok')"`
- **通过标准**：ruff 无告警；import 成功输出 `shared-ok`。
- **人工确认点**：检查 `src/qipei_agent/shared/errors.py` 确认五个错误码与 spec §3.5 一致（E_KINGDEE_TIMEOUT/E_PIM_UNAVAILABLE/E_NOT_FOUND/E_LLM_FAILED/E_RATE_LIMIT）。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/shared/`。
- **commit message**：`feat(plan-P1-3): shared 基础设施`

> ⏸ 里程碑边界：完成 M1 全部步骤（P1-1~P1-3）后暂停，输出里程碑报告（src 骨架/配置/shared 就绪、依赖可装、ci.yml 可提交、配置可载），经用户人工放行后再继续 M2。

---

### 里程碑 M2：数据模型与集成层/ETL

#### 步骤 P2-1：MySQL 数据模型（10 表 schema）
- **目标**：按 spec §3.4 建立 10 张主数据中心表的 ORM 模型与部署 DDL。
- **读取文件**：`spec.md`（§3.3、§3.4）、`ADR-04.md`、`ADR-15.md`、`ADR-20.md`、`ADR-21.md`、`ADR-26.md`、`ADR-27.md`、`ADR-32.md`、`ADR-36.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/shared/db.py`（SQLAlchemy 2.x 模型）、`qipei-agent/deploy/schema.sql`（DDL，部署初始化，不入包）。
- **数据契约**：输入 spec §3.4 表×字段表；输出 10 表 ORM 模型 + DDL。
- **依赖**：spec §3.3、§3.4；ADR-04/15/20/21/26/27/32/36；步骤 P1-1、P1-3。
- **实现要点**：① 10 表逐字段照抄 spec §3.4：product/customer/oe_mapping/fitment/stock/purchase_order/supplier_material/supplier_month_max/price/audit_log；② `oe_mapping` 含 `oe_base`（宽松匹配基号列，ADR-15）+ `oe_type`（原厂/REF）；③ `audit_log` 字段 {request_id,user_id,role,intent,query,hit_count,is_fallback,created_at}（ADR-32）；④ 主键/外键/索引按 spec 字段语义建立（如 oe_normalized 唯一、sku_code 索引）；不引入 spec 未列字段；⑤ DDL 落 deploy/schema.sql（部署工件，不入包），与 ORM 模型字段一致。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/shared/db.py && python -c "from qipei_agent.shared.db import Base; print(sorted(Base.metadata.tables.keys()))"`
- **通过标准**：ruff 无告警；输出含全部 10 表名。
- **人工确认点**：检查输出表名集合恰好为 spec §3.4 的 10 张表，无多无少；抽查 oe_mapping 含 oe_base/oe_type、audit_log 含 is_fallback；确认 schema.sql 与 ORM 字段一致。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/shared/db.py qipei-agent/deploy/schema.sql`。
- **commit message**：`feat(plan-P2-1): MySQL 10 表数据模型`

#### 步骤 P2-2：集成层-金蝶客户端（executeBillQuery + 鉴权 + 兜底表单）
- **目标**：实现金蝶集成客户端：executeBillQuery 通用查询、KDSpaceToken 鉴权与刷新、并发≤10/429 退避、5 兜底表单查询、OE 兜底 BD_MATERIAL_OE_EXT。
- **读取文件**：`spec.md`（§3.5、§3.6、§3.7）、`ADR-16.md`、`ADR-22.md`、`ADR-23.md`、`ADR-28.md`、`ADR-29.md`、`ADR-35.md`、`ADR-41.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/integration/kingdee.py`、`qipei-agent/tests/integration/test_integration_kingdee.py`。
- **数据契约**：输入 spec §3.5 集成层金蝶契约（FormId/FieldKeys/FilterString/TopRowCount 等）+ §3.6 超时/重试默认值；输出 executeBillQuery(form_id, field_keys, filter_string, limit) → rows + 5 兜底表单查询函数 + OE 兜底查询 + token 刷新。
- **依赖**：spec §3.5、§3.6、§3.7；ADR-16/22/23/28/29/35/41；步骤 P1-1、P1-3。
- **实现要点**：① executeBillQuery：POST 金蝶，body {FormId,FieldKeys,FilterString,OrderString,TopRowCount,StartRow,Limit}，鉴权 Authorization: KDSpaceToken {token}，解析 Result.IsSuccess/Rows/TotalCount（ADR-16）；② token 刷新：POST /AuthService.RefreshToken {refreshToken}→新 access+refresh+expiry，401 触发重刷+重试（ADR-29）；③ 并发≤10，429 读 Retry-After（无则 5s），重试 3 次指数退避 backoff 1s×2 封顶 30s（ADR-22/23）；④ **只读禁写**：仅 executeBillQuery 查询，无任何写接口（红线 ADR-16）；⑤ 5 兜底表单 BD_MATERIAL/BD_CUSTOMER/BD_MATERIALSUPPLIER/PUR_PURCHASEORDER/SAL_PRICEBASE（limit=20，ADR-28）；⑥ OE 兜底 BD_MATERIAL_OE_EXT（FOENO LIKE '%{oe}%'，单 OE，分页 FRowIndex，ADR-35）；现货取 FAVAILABLEQTY（ADR-17）；⑦ 外部依赖（网络客户端/令牌/时钟）按 ADR-41 注入。所有外部调用参数与字段名照抄 ADR，不臆造。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/integration/kingdee.py && pytest tests/integration/test_integration_kingdee.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（用 httpx mock 模拟金蝶响应与 429/401，不连真实金蝶）。
- **人工确认点**：检查 `kingdee.py` 中**无任何 write/audit/save/bill 保存类调用**（红线），仅有 executeBillQuery；确认 5 兜底表单与 ADR-28 一致、OE 兜底 FormId=BD_MATERIAL_OE_EXT。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/integration/kingdee.py qipei-agent/tests/integration/test_integration_kingdee.py`。
- **commit message**：`feat(plan-P2-2): 金蝶集成客户端与兜底表单`

#### 步骤 P2-3：集成层-PIM 客户端（oe-vehicle + 鉴权刷新）
- **目标**：实现 PIM 集成客户端：GET oe-vehicle 主数据查询、Bearer 鉴权与刷新。
- **读取文件**：`spec.md`（§3.5、§3.6、§3.7）、`ADR-20.md`、`ADR-22.md`、`ADR-29.md`、`ADR-41.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/integration/pim.py`、`qipei-agent/tests/integration/test_integration_pim.py`。
- **数据契约**：输入 spec §3.5 PIM 契约；输出 get_oe_vehicle(material_code?, oe_no?, page, page_size≤500) → records[]{pimId,materialCode,productCategory,updateTime,oeList[],vehicleAdaptList[]}。
- **依赖**：spec §3.5、§3.6、§3.7；ADR-20/22/29/41；步骤 P1-1、P1-3。
- **实现要点**：① GET /api/pim/adapt/oe-vehicle，Bearer 鉴权，params page/pageSize(≤500)/materialCode/oeNo（ADR-20）；② 返回结构照抄 ADR-20（records 含 oeList[]{oeRaw,oeNormalized,oeBrand,oeRemark} + vehicleAdaptList[]{brand,series,model,engineCode,yearStart,yearEnd,chassisCode,note}）；③ token 刷新：POST /pim/api/v1/auth/refresh，header Bearer {旧token}，body {refresh_token}→新 access+refresh，业务鉴权 Authorization: Bearer {网关access_token}，401 重刷+重试（ADR-29）；④ 重试/超时参数对称金蝶（ADR-22）；⑤ **ETL 重归一化自权威**：PIM 的 oeNormalized 仅用于对账告警，不直接入库（ADR-20）；oe_type 取自 oeRemark（含 REF→REF 否则原厂）；⑥ 外部依赖（网络客户端/令牌）按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/integration/pim.py && pytest tests/integration/test_integration_pim.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（httpx mock PIM 响应 + 401 刷新重试）。
- **人工确认点**：检查返回结构字段名与 ADR-20 完全一致；确认 token 刷新端点/header 与 ADR-29 一致。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/integration/pim.py qipei-agent/tests/integration/test_integration_pim.py`。
- **commit message**：`feat(plan-P2-3): PIM 集成客户端`

#### 步骤 P2-4：ETL 抽取/归一化/装载
- **目标**：实现 ETL 管道：extract（调集成层）→ normalize_oe/normalize_fitment（重归一化）→ load（幂等 upsert 到 MySQL），按 spec §3.4 频率。
- **读取文件**：`spec.md`（§3.4、§3.5）、`ADR-15.md`、`ADR-20.md`、`ADR-21.md`、`ADR-26.md`、`ADR-27.md`、`ADR-32.md`、`ADR-36.md`、`ADR-41.md`、`qipei-agent/src/qipei_agent/integration/kingdee.py`、`qipei-agent/src/qipei_agent/integration/pim.py`（P2-2/P2-3 产出）、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/etl/extract.py`、`qipei-agent/src/qipei_agent/etl/normalize_oe.py`、`qipei-agent/src/qipei_agent/etl/normalize_fitment.py`、`qipei-agent/src/qipei_agent/etl/load.py`、`qipei-agent/tests/etl/test_etl.py`。
- **数据契约**：输入 spec §3.4 频率表 + §3.5 OE/车型/价格/交期归一化规则；输出按频率同步的 ETL 任务（每日全量：OE/车型/采购周期/供应商交期/默认供应商/历史供货量；5min 增量：库存/在途 PO；1h 全量：分级价）。
- **依赖**：spec §3.4、§3.5；ADR-15/20/21/26/27/32/36/41；步骤 P2-1、P2-2、P2-3。
- **实现要点**：① 频率严格照抄 ADR-32（库存/在途 5min 增量、价格 1h 全量、其余每日全量）；② 幂等 upsert：主键 sku_code 或 oe_normalized（ADR-32）；③ normalize_oe 复用 ADR-15 流水线（与 P3-2 同源规则，规则读 config/oe_normalize.yaml）；④ normalize_fitment：engine_code 大写去空格、year 落区间、brand 经 brand_normalize.yaml 映射（ADR-21）；⑤ 历史供货量 ETL 自金蝶视图 V_MATERIAL_SUPPLIER_MONTH_MAX_QTY→supplier_month_max（近 12 月月度最大，ADR-36）；⑥ 失败重试按 ADR-22，最终失败告警；⑦ 调度方式用 cron/调度器（具体调度器不指定，落 deploy 侧）；⑧ 网络客户端/文件 IO 依赖按 ADR-41 注入。不引入 spec 外依赖。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/etl/ && pytest tests/etl/test_etl.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（mock 集成层返回，验证 upsert 幂等与归一化结果）。
- **人工确认点**：检查频率表与 ADR-32 一致；确认 upsert 主键为 sku_code/oe_normalized；确认 normalize 复用 config 规则未硬编码。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/etl/ qipei-agent/tests/etl/test_etl.py`。
- **commit message**：`feat(plan-P2-4): ETL 抽取/归一化/装载`

> ⏸ 里程碑边界：完成 M2 全部步骤（P2-1~P2-4）后暂停，输出里程碑报告（10 表就绪、金蝶/PIM 客户端单测绿、ETL 管道就绪），经用户人工放行后再继续 M3。

---

### 里程碑 M3：能力层（6 工具 + 权限过滤）

#### 步骤 P3-1：能力层 main + 统一信封 + 路由骨架
- **目标**：搭建 capability FastAPI 应用：统一端点 POST /api/v1/tools/{tool}、X-Request-Id 中间件、统一信封响应、请求校验（必含 user_id+role）。
- **读取文件**：`spec.md`（§3.5）、`ADR-30.md`、`ADR-34.md`、`ADR-22.md`、`qipei-agent/src/qipei_agent/shared/`（P1-3）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/main.py`、`qipei-agent/src/qipei_agent/capability/envelope.py`、`qipei-agent/tests/capability/test_capability_main.py`。
- **数据契约**：输入 spec §3.5 能力层 HTTP 契约；输出统一信封 {request_id,ok,data|error{code,message}}，6 工具路由占位。
- **依赖**：spec §3.5；ADR-30/34/22；步骤 P1-1、P1-3。
- **实现要点**：① FastAPI 应用，路由 POST /api/v1/tools/{tool}（tool∈6 工具名，未知 tool→E_NOT_FOUND）；② 中间件读取 X-Request-Id（无则生成），注入 request_id 并透传到响应与日志（ADR-22）；③ 统一信封包装函数：成功 {request_id,ok:true,data}，失败 {request_id,ok:false,error{code,message}}（ADR-30/34）；④ 请求校验：body 必含 user_id+role，缺失→E_* 错误（ADR-34：权限过滤在能力层，请求须携带）；⑤ 6 工具 handler 占位（后续步骤填充），先返回信封骨架。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/ && pytest tests/capability/test_capability_main.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（测信封格式、X-Request-Id 透传、缺 user_id/role 报错、未知 tool 报错）。
- **人工确认点**：检查 test 覆盖：信封字段、request_id 透传、user_id+role 缺失校验、未知 tool→E_NOT_FOUND。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/main.py qipei-agent/src/qipei_agent/capability/envelope.py qipei-agent/tests/capability/test_capability_main.py`。
- **commit message**：`feat(plan-P3-1): 能力层 main 与统一信封`

#### 步骤 P3-2：normalize_oe 工具
- **目标**：实现 OE 归一化工具（ADR-15 流水线）。
- **读取文件**：`spec.md`（§3.5）、`ADR-15.md`、`qipei-agent/config/oe_normalize.yaml`（P1-2）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/normalize_oe.py`、`qipei-agent/tests/capability/test_normalize_oe.py`。
- **数据契约**：输入 {oe_raw}（+user_id,role）；输出 {oe_normalized, is_valid}（ADR-34）。
- **依赖**：spec §3.5；ADR-15/34；步骤 P1-2、P3-1。
- **实现要点**：① 流水线严格按 ADR-15：trim→大写→去前缀（长度降序+边界，无标点前缀后须紧跟非字母数字或结尾，防 OEM123 误删）→去非字母数字（只留 [A-Z0-9]）→纯数字去前导零→全 0 标记无效；② 规则全部读 config/oe_normalize.yaml，不硬编码；③ oe_test_samples.md 的 26 样本作为测试断言依据（如 0986479012→986479012、43206-3JA0A→432063JA0A、0 986 479 012→986479012、6Q0820803C≠6Q0820803）；④ 前缀清单 8 项大写长度降序。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/normalize_oe.py && pytest tests/capability/test_normalize_oe.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（26 样本 + 前缀/分隔符/前导零/大写变体 + 全0 无效，结果与 oe_test_samples 预期一致）。
- **人工确认点**：检查 26 样本测试断言与 oe_test_samples.md 关键示例逐项对应；确认 6Q0820803C 与 6Q0820803 断言为不同结果。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/normalize_oe.py qipei-agent/tests/capability/test_normalize_oe.py`。
- **commit message**：`feat(plan-P3-2): normalize_oe 工具`

#### 步骤 P3-3：search_by_oe 工具（含 ERP 兜底）
- **目标**：实现 OE→SKU 检索 + miss 时 ERP 兜底（ADR-35）。
- **读取文件**：`spec.md`（§3.4、§3.5）、`ADR-15.md`、`ADR-20.md`、`ADR-28.md`、`ADR-35.md`、`ADR-04.md`、`ADR-41.md`、`qipei-agent/src/qipei_agent/integration/kingdee.py`（P2-2）、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/oe_search.py`、`qipei-agent/tests/capability/test_search_by_oe.py`。
- **数据契约**：输入 {oe_normalized, loose}（+user_id,role）；输出 {skus:[{sku_code,name,oe_raw,oe_type,label,image_url,fitments}]}（ADR-34）。
- **依赖**：spec §3.4、§3.5；ADR-04/15/20/28/35/34/41；步骤 P2-1、P2-2、P3-1、P3-2。
- **实现要点**：① 主检索查 MySQL oe_mapping（PIM 来源，ADR-04）：精确模式 oe_normalized 全等；宽松模式（loose=true）匹配 oe_base（去末尾字母基号，ADR-15），返回须同时展示原始完整 OE 并标注【宽松匹配，已剔除末尾后缀字母，请业务员复核】；② 多 SKU 排序：原厂 OE 优先、REF 靠后、同类型 sku_code 升序，带【原厂 OE】【REF 参考号】标签（ADR-15）；③ **miss 触发兜底**（ADR-35）：调集成层 BD_MATERIAL_OE_EXT FOENO LIKE '%{oe}%'（单 OE，limit=20），兜底**只查金蝶**（关联物料/客户/供应商/PO/价格表，不实时打 PIM）；④ 兜底结果降权靠后并标注（通过 label 体现，spec §3.5「金蝶兜底靠后并标注」）；⑤ 主检索结果优先、金蝶兜底靠后；耗时计入 P95；⑥ 调集成层为网络依赖，按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/oe_search.py && pytest tests/capability/test_search_by_oe.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（命中/未命中/兜底/多 SKU 排序/宽松模式标注）。
- **人工确认点**：检查兜底分支**只调金蝶**（无 PIM 实时调用）；确认多 SKU 排序与标签符合 ADR-15；确认宽松结果带复核标注。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/oe_search.py qipei-agent/tests/capability/test_search_by_oe.py`。
- **commit message**：`feat(plan-P3-3): search_by_oe 与 ERP 兜底`

#### 步骤 P3-4：search_by_fitment 工具
- **目标**：实现车型→SKU 检索（ADR-21）。
- **读取文件**：`spec.md`（§3.4、§3.5）、`ADR-21.md`、`ADR-28.md`、`ADR-04.md`、`ADR-41.md`、`qipei-agent/config/brand_normalize.yaml`（P1-2）、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/fitment_search.py`、`qipei-agent/tests/capability/test_search_by_fitment.py`。
- **数据契约**：输入 {brand, series, model, year}（+user_id,role）；输出 {skus:[{sku_code,name,oe_list,image_url}]}（ADR-34）。
- **依赖**：spec §3.4、§3.5；ADR-04/21/28/34/41；步骤 P2-1、P3-1。
- **实现要点**：① 主检索查 MySQL fitment 表；brand 经 brand_normalize.yaml 映射后精确匹配；series 精确（二级必须）；model 精确（忽略大小写/去空格）；year 落区间 [year_start,year_end]；engine_code 可选（ADR-21）；② **不用模糊匹配**（ADR-21）；③ miss 触发兜底（ADR-28，调集成层金蝶表单）；④ 返回 oe_list 含 oe_type/label（ADR-34）；⑤ 调集成层为网络依赖，按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/fitment_search.py && pytest tests/capability/test_search_by_fitment.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（brand 映射/区间命中/未命中/兜底）。
- **人工确认点**：确认检索为全精确匹配（无模糊）；确认 brand 经映射；确认 year 落区间。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/fitment_search.py qipei-agent/tests/capability/test_search_by_fitment.py`。
- **commit message**：`feat(plan-P3-4): search_by_fitment`

#### 步骤 P3-5：get_stock 工具
- **目标**：实现库存查询（ADR-17/34）。
- **读取文件**：`spec.md`（§3.4、§3.5）、`ADR-17.md`、`ADR-07.md`、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/stock.py`、`qipei-agent/tests/capability/test_get_stock.py`。
- **数据契约**：输入 {sku_code}（+user_id,role）；输出 {sku_code, on_hand}（ADR-34，on_hand=FAVAILABLEQTY）。
- **依赖**：spec §3.4、§3.5；ADR-17/34/07；步骤 P2-1、P3-1、P3-8。
- **实现要点**：① 查 MySQL stock 表 on_hand（ETL 自金蝶 FAVAILABLEQTY，ADR-17）；② get_stock miss **不兜底**，直接 E_NOT_FOUND（spec §3.5：get_stock miss 不兜底）；③ 库存对仓库开放（ADR-07/13）。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/stock.py && pytest tests/capability/test_get_stock.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（命中/未命中→E_NOT_FOUND）。
- **人工确认点**：确认 on_hand 来自 stock 表（FAVAILABLEQTY）；确认 miss 不兜底直接报错。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/stock.py qipei-agent/tests/capability/test_get_stock.py`。
- **commit message**：`feat(plan-P3-5): get_stock`

#### 步骤 P3-6：get_price 工具
- **目标**：实现分级价查询（ADR-26/34）。
- **读取文件**：`spec.md`（§3.3、§3.5）、`ADR-26.md`、`ADR-34.md`、`ADR-07.md`、`qipei-agent/config/customer_level.yaml`（P1-2）、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/price.py`、`qipei-agent/tests/capability/test_get_price.py`。
- **数据契约**：输入 {sku_code, customer_id, quantity}（+user_id,role）；输出 {price, tax_included, original_price, currency, customer_tier, price_type, qty_range}（ADR-34）。
- **依赖**：spec §3.5；ADR-26/34/07；步骤 P1-2、P2-1、P3-1、P3-8。
- **实现要点**：① customer_tier 从 MySQL customer 表取（ETL 自 BD_CUSTOMER.FCUSTLEVELID→BD_CUSTLEVEL.FNAME→customer_level.yaml→A/B/C/D），**不实时打金蝶 BD_CUSTOMER**（ADR-26）；② 命中优先级：客户专属价 > 等级价 > 人工询价；③ 阶梯 FQTYLOW~FQTYHIGH，按 quantity 命中区间，超上限取最大阶梯+提示；④ 含税 FISINCLUDETAX 对外统一含税显示 + original_price 未税价；⑤ 币种以 price 表命中行 currency 为准，**请求不带 currency，不换算**（ADR-26/34）；⑥ price_type∈{专属价,等级价,人工询价}；⑦ get_price miss 不兜底直接 E_NOT_FOUND；⑧ 价格本 FormId=SAL_PRICEBASE（非 BD_PriceBase）、数量字段 FQTYLOW/FQTYHIGH（非 MIN/MAX）—— ETL 侧已落表，此处只读 MySQL。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/price.py && pytest tests/capability/test_get_price.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（优先级/阶梯命中/超上限取最大/含税与未税/币种不换算/无 customer_id 跳过逻辑由编排层负责此处不测）。
- **人工确认点**：确认优先级链与阶梯口径与 ADR-26 一致；确认 customer_tier 取自 MySQL customer 表（无金蝶实时调用）。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/price.py qipei-agent/tests/capability/test_get_price.py`。
- **commit message**：`feat(plan-P3-6): get_price 分级价`

#### 步骤 P3-7：calc_lead_time 工具
- **目标**：实现交期计算（ADR-17/27/37）。
- **读取文件**：`spec.md`（§3.4、§3.5）、`ADR-17.md`、`ADR-27.md`、`ADR-37.md`、`ADR-36.md`、`ADR-06.md`、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/lead_time.py`、`qipei-agent/tests/capability/test_calc_lead_time.py`。
- **数据契约**：输入 {sku_code, quantity}（+user_id,role）；输出 {lead_time, split:[{segment,qty,lead_time,arrival_date?}], supplier_note, risk_level, risk_hint, pos, alternatives}（ADR-34/37）。
- **依赖**：spec §3.4、§3.5；ADR-06/17/27/37/36；步骤 P2-1、P3-1、P3-8。
- **实现要点**：① 三分支：有现货→现货交期（默认1天，物料可覆盖）；现货不足→现货部分1天+缺口走「在途→采购」；无现货→有在途取在途交期，否则采购周期（FLEADTIME，兜底15天）+供应商交期（ADR-17）；② 在途：多笔 PO 按 FPLANARRIVALDATE 升序取最早，数量不足拆分（ADR-27）；在途数量主路径用 PIM PO FNOTRECEIVEQTY（ETL 已落表），兜底用金蝶 FQTY-FRECEIVEQTY（FDOCUMENTSTATUS=C，ADR-17）；③ 供应商交期：默认供应商（FISDEFAULTSUPPLIER=1）优先；无默认取最短+标注非默认风险（ADR-27）；④ split 分段 {segment∈{现货,在途,采购}, qty, lead_time, arrival_date?}，main lead_time=max（ADR-37）；⑤ risk：非默认→medium；需求量>supplier_month_max.max_month_qty→high；>30天→长周期；无历史→medium+提示（ADR-27/36）；⑥ pos 列出在途 PO（供应商/到货日/数量），alternatives 列备选供应商；⑦ **红线**：交期采纳权在人，零自动落库（ADR-06）——本工具只计算返回，不写任何表。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/lead_time.py && pytest tests/capability/test_calc_lead_time.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（三分支/现货不足拆分/多PO升序+不足拆分/默认供应商优先+无默认取最短/risk 等级）。
- **人工确认点**：确认 split 结构与 ADR-37 一致；确认 main=max；确认无任何写操作（红线）。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/lead_time.py qipei-agent/tests/capability/test_calc_lead_time.py`。
- **commit message**：`feat(plan-P3-7): calc_lead_time 三分支交期`

#### 步骤 P3-8：权限过滤（能力层落点）
- **目标**：在能力层各工具返回前按 ADR-07 矩阵过滤字段（敏感数据不出内网到编排层）。
- **读取文件**：`spec.md`（§3.5、§6）、`ADR-07.md`、`ADR-13.md`、`ADR-34.md`、`qipei-agent/src/qipei_agent/shared/permissions.py`（P1-3）、`qipei-agent/config/permission.yaml`（P1-2）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/capability/permission_filter.py`、`qipei-agent/tests/capability/test_permission_filter.py`。
- **数据契约**：输入 role（来自请求 body）+ 工具原始响应；输出过滤后响应（按角色隐藏字段）。
- **依赖**：spec §3.5、§6；ADR-07/13/34；步骤 P1-2、P1-3、P3-3~P3-7。
- **实现要点**：① 过滤落点在能力层（内网），非编排层（ADR-34：敏感数据价格/供应商备注/备选交期不出内网）；② 按 ADR-07 矩阵：业务员/跟单全量；售后隐藏供应商备注+备选供应商交期（可见主交期）；仓库仅库存/SKU/品名/库位/图片/车型适配（隐藏所有交期/价格/供应商备注/客户等级）；③ 复用 qipei_agent.shared.permissions.filter_fields + config/permission.yaml；④ 在各工具 handler 返回前调用过滤（接入 P3-3~P3-7，本步聚焦过滤逻辑与矩阵测试）。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/capability/permission_filter.py && pytest tests/capability/test_permission_filter.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（仓库角色查同一 SKU 价格字段不出现；售后无供应商备注/备选交期；业务员/跟单全量）。
- **人工确认点**：确认过滤矩阵与 ADR-07 逐角一致；确认过滤发生在能力层（非编排层）。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/capability/permission_filter.py qipei-agent/tests/capability/test_permission_filter.py`。
- **commit message**：`feat(plan-P3-8): 能力层权限过滤`

> ⏸ 里程碑边界：完成 M3 全部步骤（P3-1~P3-8）后暂停，输出里程碑报告（6 工具 + 权限过滤单测全绿、红线零写已验证、敏感数据不出内网已验证），经用户人工放行后再继续 M4。

---

### 里程碑 M4：编排层

#### 步骤 P4-1：编排层 main + 入口契约 + Redis 会话 + 审计写入
- **目标**：实现 orchestrator FastAPI 应用：POST /api/v1/chat 入口、信任调用方、Redis 会话管理、审计日志写入。
- **读取文件**：`spec.md`（§3.5、§6）、`ADR-25.md`、`ADR-33.md`、`ADR-32.md`、`ADR-13.md`、`ADR-41.md`、`qipei-agent/src/qipei_agent/shared/`（P1-3）、`qipei-agent/src/qipei_agent/shared/db.py`（P2-1）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/orchestrator/main.py`、`qipei-agent/src/qipei_agent/orchestrator/session.py`、`qipei-agent/src/qipei_agent/orchestrator/audit.py`、`qipei-agent/tests/orchestrator/test_orchestrator_main.py`。
- **数据契约**：输入 POST /api/v1/chat {session_id?, message, context{user_id,role,customer_id?,currency?,quantity?}}；输出 {session_id, request_id, intent, answer{...}}（ADR-25）。审计写入 audit_log（§3.4 字段）。
- **依赖**：spec §3.5、§6；ADR-25/33/32/13/41；步骤 P1-1、P1-3、P2-1、P3-1。
- **实现要点**：① 入口 POST /api/v1/chat，**信任调用方**（不做鉴权重校，ADR-25）；② Redis 会话 key `session:{id}`，value {intent,params,last_query,history:[最多10条]}，TTL 30min（ADR-33）；无 session_id 则生成；③ 从 context 透传 user_id+role（+customer_id/quantity）给能力层工具调用；④ **审计写入**：在 /chat 处理末尾写 audit_log 行 {request_id,user_id,role,intent,query,hit_count,is_fallback,created_at}（字段语义见 §3.4/ADR-32；其中 intent/query/hit_count/is_fallback 为编排层运行时值——见风险清单 R1）；⑤ 审计脱敏：只记查询动作+命中数，**不记价格/库存具体数值**（ADR-32）；⑥ 调用能力层的网络地址属部署侧（residual #3，转人工），本步用配置占位（不引入 spec 外 env 变量）；⑦ Redis/时钟等外部依赖按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/orchestrator/ && pytest tests/orchestrator/test_orchestrator_main.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（会话创建/续期/TTL、审计行写入且不含价格/库存数值、context 透传）。
- **人工确认点**：检查 audit_log 写入字段与 §3.4 一致；确认审计行**不含** price/on_hand 数值（脱敏）；确认会话 value 结构与 ADR-33 一致、TTL=30min。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/orchestrator/main.py qipei-agent/src/qipei_agent/orchestrator/session.py qipei-agent/src/qipei_agent/orchestrator/audit.py qipei-agent/tests/orchestrator/test_orchestrator_main.py`。
- **commit message**：`feat(plan-P4-1): 编排层入口与会话审计`

#### 步骤 P4-2：意图识别（4 意图）
- **目标**：实现意图分类（oe_query/fitment_query/lead_time_query/composite_query）。
- **读取文件**：`spec.md`（§3.5）、`ADR-33.md`、`ADR-31.md`、`ADR-41.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/orchestrator/intent.py`、`qipei-agent/tests/orchestrator/test_intent.py`。
- **数据契约**：输入 message（+会话上下文）；输出 intent∈{oe_query,fitment_query,lead_time_query,composite_query}。
- **依赖**：spec §3.5；ADR-33/31/41；步骤 P4-1。
- **实现要点**：① 规则优先识别意图（正则+词典）；② miss 降级豆包 function calling（llm_timeout 2s，超时降级模板回答「无法自动识别，请换种说法或人工查询」，ADR-31/33）；③ 4 意图照抄 ADR-33；④ LLM 依赖按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/orchestrator/intent.py && pytest tests/orchestrator/test_intent.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（4 意图正确分类 + LLM 兜底 mock + 超时降级模板）。
- **人工确认点**：确认 4 意图集合与 ADR-33 一致；确认 llm_timeout=2s（非 5s）。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/orchestrator/intent.py qipei-agent/tests/orchestrator/test_intent.py`。
- **commit message**：`feat(plan-P4-2): 意图识别`

#### 步骤 P4-3：参数抽取（规则优先 + 豆包兜底）
- **目标**：实现参数抽取（OE 正则/品牌词典/车系/车型/年份/数量）。
- **读取文件**：`spec.md`（§3.5）、`ADR-33.md`、`ADR-15.md`、`ADR-21.md`、`ADR-41.md`、`qipei-agent/config/brand_normalize.yaml`（P1-2）。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/orchestrator/param_extract.py`、`qipei-agent/tests/orchestrator/test_param_extract.py`。
- **数据契约**：输入 message+intent；输出 params（依意图：oe_normalized/loose 或 brand/series/model/year 或 sku_code/quantity）。
- **依赖**：spec §3.5；ADR-33/15/21/41；步骤 P1-2、P4-1、P4-2。
- **实现要点**：① 规则优先：OE 正则识别→归一化（调能力层 normalize_oe）；车型品牌（brand_normalize 词典）+车系+车型+4 位年份数字；数量（数字+件/套单位）（ADR-33）；② miss 降级豆包 function calling，llm_timeout 2s 超时降级模板（ADR-31）；③ 缺 year/series/model 或 OE 无结果→触发追问（ADR-31）；④ 抽取结果写入会话 params；⑤ LLM 依赖按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/orchestrator/param_extract.py && pytest tests/orchestrator/test_param_extract.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（各意图参数抽取 + 缺项追问 + LLM 兜底 mock + 超时降级）。
- **人工确认点**：确认参数抽取规则项与 ADR-33 一致（OE/品牌/车系/车型/年份/数量）；确认追问条件与 ADR-31 一致。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/orchestrator/param_extract.py qipei-agent/tests/orchestrator/test_param_extract.py`。
- **commit message**：`feat(plan-P4-3): 参数抽取`

#### 步骤 P4-4：工具调度
- **目标**：实现工具调度顺序 OE→SKU→库存→价格→交期（ADR-33）。
- **读取文件**：`spec.md`（§3.5、§6）、`ADR-33.md`、`ADR-26.md`、`ADR-13.md`、`ADR-41.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/orchestrator/tool_dispatch.py`、`qipei-agent/tests/orchestrator/test_tool_dispatch.py`。
- **数据契约**：输入 intent+params+context；输出聚合的工具结果（供 answer_render）。
- **依赖**：spec §3.5、§6；ADR-33/26/13/41；步骤 P3-1（能力层契约）、P4-1、P4-2、P4-3。
- **实现要点**：① 调度顺序照抄 ADR-33：OE→SKU→库存→价格→交期；② **无 customer_id 时跳过 get_price**，回答价格位标注「未提供客户，无法报价」（ADR-26）；③ 调能力层 POST /api/v1/tools/{tool}，透传 user_id+role+X-Request-Id；④ 能力层返回已过滤数据（权限在能力层，编排层不再过滤）；⑤ LLM 只做意图/抽参/工具选择，**不接触价格/库存/报价数值**（ADR-13）——数值只来自能力层结构化响应；⑥ 调能力层的 HTTP 客户端为网络依赖，按 ADR-41 注入。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/orchestrator/tool_dispatch.py && pytest tests/orchestrator/test_tool_dispatch.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（调度顺序正确、无 customer_id 跳过价格、能力层 mock）。
- **人工确认点**：确认调度顺序与 ADR-33 一致；确认无 customer_id 时跳过 get_price 且标注「未提供客户，无法报价」。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/orchestrator/tool_dispatch.py qipei-agent/tests/orchestrator/test_tool_dispatch.py`。
- **commit message**：`feat(plan-P4-4): 工具调度`

#### 步骤 P4-5：回答渲染（固定模板）
- **目标**：实现固定结构回答模板（ADR-13/33）。
- **读取文件**：`spec.md`（§3.5、§6）、`ADR-13.md`、`ADR-33.md`、`ADR-31.md`。
- **修改/新建文件**：`qipei-agent/src/qipei_agent/orchestrator/answer_render.py`、`qipei-agent/tests/orchestrator/test_answer_render.py`。
- **数据契约**：输入 聚合工具结果+intent+params；输出 answer{...}（固定结构：SKU 列表+车型+图片+库存+价格+交期+risk 标签）。
- **依赖**：spec §3.5、§6；ADR-13/33/31；步骤 P4-1~P4-4。
- **实现要点**：① 固定结构模板：SKU 列表 + 车型 + 图片 + 库存 + 价格 + 交期 + risk 标签（ADR-13/33）；② **模板拼接不调 LLM**（ADR-31：回答模板化）；③ OE 无结果路径：提示未找到→兜底→仍无→建议宽松匹配或换车型查（ADR-31，建议为文案提示，宽松匹配默认关见风险清单 R2）；④ 多 SKU 直接返回列表不追问（ADR-31）。
- **验证命令**：`cd qipei-agent && ruff check src/qipei_agent/orchestrator/answer_render.py && pytest tests/orchestrator/test_answer_render.py -v`
- **通过标准**：ruff 无告警；pytest 全绿（模板字段齐全、无 LLM 调用、OE 无结果建议文案、多 SKU 列表）。
- **人工确认点**：确认回答结构含 SKU/车型/图片/库存/价格/交期/risk；确认渲染过程无 LLM 调用。
- **回退方式**：`git checkout -- qipei-agent/src/qipei_agent/orchestrator/answer_render.py qipei-agent/tests/orchestrator/test_answer_render.py`。
- **commit message**：`feat(plan-P4-5): 回答模板渲染`

> ⏸ 里程碑边界：完成 M4 全部步骤（P4-1~P4-5）后暂停，输出里程碑报告（入口/会话/审计/意图/抽参/调度/模板单测全绿、LLM 边界已验证、红线零写已验证），经用户人工放行后再继续 M5。

---

### 里程碑 M5：测试与验收

#### 步骤 P5-1：OE 归一化完整测试
- **目标**：固化 26 样本+变体+全0 的归一化测试断言（ADR-24/15）。
- **读取文件**：`qipei-agent/tests/oe_test_samples.md`（样本源）、`spec.md`（§4.3）、`ADR-15.md`、`ADR-24.md`、`qipei-agent/tests/capability/test_normalize_oe.py`（P3-2 已建，本步扩充）。
- **修改/新建文件**：`qipei-agent/tests/capability/test_normalize_oe.py`（扩充用例）。
- **数据契约**：输入 oe_test_samples.md 26 样本 + 关键示例；输出测试断言（输入→预期 oe_normalized/is_valid）。
- **依赖**：spec §4.3；ADR-15/24；步骤 P3-2。
- **实现要点**：① 26 样本逐条断言（按 ADR-15 流水线计算预期值，与业务方抽样核对固化）；② 变体：前缀/分隔符/前导零/大写变体；③ 全0（如 000）→ is_valid=false；④ 6Q0820803C 与 6Q0820803 断言为不同结果。
- **验证命令**：`cd qipei-agent && pytest tests/capability/test_normalize_oe.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：抽样核对 5 条样本断言与 tests/oe_test_samples.md 关键示例一致（含 0986479012→986479012、0 986 479 012→986479012）。
- **回退方式**：`git checkout -- qipei-agent/tests/capability/test_normalize_oe.py`。
- **commit message**：`test(plan-P5-1): OE 归一化 26 样本`

#### 步骤 P5-2：brand 归一化测试
- **目标**：固化 brand 映射测试（ADR-24/21）。
- **读取文件**：`qipei-agent/config/brand_normalize.yaml`（P1-2）、`ADR-21.md`、`ADR-24.md`。
- **修改/新建文件**：`qipei-agent/tests/shared/test_brand_normalize.py`。
- **数据契约**：输入 brand_normalize.yaml 键值；输出映射断言（含兜底 ""/null→UNKNOWN）。
- **依赖**：spec §4.3；ADR-21/24；步骤 P1-2、P1-3。
- **实现要点**：① 逐键值断言（大众/Volkswagen/vw→VW 等）；② 兜底 ""/null→UNKNOWN；③ 大小写/别名覆盖。
- **验证命令**：`cd qipei-agent && pytest tests/shared/test_brand_normalize.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认断言覆盖 brand_normalize.yaml 全部键与兜底。
- **回退方式**：`git checkout -- qipei-agent/tests/shared/test_brand_normalize.py`。
- **commit message**：`test(plan-P5-2): brand 归一化`

#### 步骤 P5-3：检索命中/未命中/兜底测试
- **目标**：固化 search_by_oe/search_by_fitment/get_stock 的命中/未命中/兜底测试（ADR-24）。
- **读取文件**：`spec.md`（§3.5、§4.1）、`ADR-24.md`、`ADR-35.md`、`ADR-28.md`。
- **修改/新建文件**：`qipei-agent/tests/capability/test_search_by_oe.py`（扩充）、`qipei-agent/tests/capability/test_search_by_fitment.py`（扩充）、`qipei-agent/tests/capability/test_get_stock.py`（扩充）。
- **数据契约**：输入 mock MySQL + mock 集成层；输出 命中/未命中/兜底断言。
- **依赖**：spec §3.5、§4.1；ADR-24/35/28；步骤 P3-3、P3-4、P3-5。
- **实现要点**：① OE 命中（主检索）/未命中→兜底（金蝶 BD_MATERIAL_OE_EXT，只查金蝶）/兜底仍无；② 车型命中/未命中/兜底；③ 库存命中/未命中→E_NOT_FOUND（不兜底）；④ 端到端命中率口径≥98%（含兜底）的用例覆盖。
- **验证命令**：`cd qipei-agent && pytest tests/capability/test_search_by_oe.py tests/capability/test_search_by_fitment.py tests/capability/test_get_stock.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认兜底分支只调金蝶（无 PIM 实时）；确认 get_stock miss 不兜底。
- **回退方式**：`git checkout -- qipei-agent/tests/capability/test_search_by_oe.py qipei-agent/tests/capability/test_search_by_fitment.py qipei-agent/tests/capability/test_get_stock.py`。
- **commit message**：`test(plan-P5-3): 检索命中/未命中/兜底`

#### 步骤 P5-4：交期三分支+多PO+供应商+risk 测试
- **目标**：固化交期计算全场景测试（ADR-24/17/27/37）。
- **读取文件**：`spec.md`（§3.5、§4.1）、`ADR-17.md`、`ADR-27.md`、`ADR-37.md`、`ADR-36.md`。
- **修改/新建文件**：`qipei-agent/tests/capability/test_calc_lead_time.py`（扩充）。
- **数据契约**：输入 mock stock/purchase_order/supplier_material/supplier_month_max；输出 三分支+拆分+risk 断言。
- **依赖**：spec §3.5、§4.1；ADR-17/27/37/36；步骤 P3-7。
- **实现要点**：① 三分支（现货/在途/采购）；② 现货不足拆分（缺口走在途→采购）；③ 多 PO 升序取最早+不足拆分；④ 默认供应商优先+无默认取最短+标注；⑤ risk（非默认 medium/超历史 high/无历史 medium+提示）；⑥ split 结构 + main=max（ADR-37 示例：需求600，现货100，在途300，缺口200）。
- **验证命令**：`cd qipei-agent && pytest tests/capability/test_calc_lead_time.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认 ADR-37 示例（需求600/现货100/在途300/缺口200）的 split 与 main 断言正确。
- **回退方式**：`git checkout -- qipei-agent/tests/capability/test_calc_lead_time.py`。
- **commit message**：`test(plan-P5-4): 交期三分支与 risk`

#### 步骤 P5-5：价格优先级/阶梯/含税测试
- **目标**：固化分级价测试（ADR-24/26）。
- **读取文件**：`spec.md`（§3.5、§4.1）、`ADR-26.md`、`ADR-24.md`。
- **修改/新建文件**：`qipei-agent/tests/capability/test_get_price.py`（扩充）。
- **数据契约**：输入 mock price/customer 表；输出 优先级/阶梯/含税/币种断言。
- **依赖**：spec §3.5、§4.1；ADR-26/24；步骤 P3-6。
- **实现要点**：① 优先级 客户专属价>等级价>人工询价；② 阶梯命中区间+超上限取最大+提示；③ 含税统一显示+original_price；④ 币种取命中行不换算；⑤ customer_tier 来自 MySQL（不实时打金蝶）。
- **验证命令**：`cd qipei-agent && pytest tests/capability/test_get_price.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认优先级链与超上限口径与 ADR-26 一致。
- **回退方式**：`git checkout -- qipei-agent/tests/capability/test_get_price.py`。
- **commit message**：`test(plan-P5-5): 价格优先级与阶梯`

#### 步骤 P5-6：权限过滤测试
- **目标**：固化 ADR-07 矩阵测试（ADR-24/07）。
- **读取文件**：`spec.md`（§6、§4.1）、`ADR-07.md`、`ADR-13.md`、`ADR-24.md`。
- **修改/新建文件**：`qipei-agent/tests/capability/test_permission_filter.py`（扩充）。
- **数据契约**：输入 4 角色×各工具响应；输出 过滤后字段集断言。
- **依赖**：spec §6、§4.1；ADR-07/13/24；步骤 P3-8。
- **实现要点**：① 仓库查同一 SKU 价格字段不出现；售后无供应商备注/备选交期；业务员/跟单全量；② 验证过滤发生在能力层。
- **验证命令**：`cd qipei-agent && pytest tests/capability/test_permission_filter.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认 4 角色矩阵与 ADR-07 逐项一致。
- **回退方式**：`git checkout -- qipei-agent/tests/capability/test_permission_filter.py`。
- **commit message**：`test(plan-P5-6): 权限过滤矩阵`

#### 步骤 P5-7：集成层 mock 测试（429/token 刷新）
- **目标**：固化集成层异常路径测试（ADR-24/22/29）。
- **读取文件**：`spec.md`（§3.7）、`ADR-22.md`、`ADR-29.md`、`ADR-24.md`、`ADR-40.md`。
- **修改/新建文件**：`qipei-agent/tests/integration/test_integration_kingdee.py`（扩充）、`qipei-agent/tests/integration/test_integration_pim.py`（扩充）。
- **数据契约**：输入 httpx mock 429/401/超时；输出 重试+token 刷新+降级断言。
- **依赖**：spec §3.7；ADR-22/29/24/40；步骤 P2-2、P2-3。
- **实现要点**：① 金蝶 429→读 Retry-After（无则 5s）+指数退避 3 次封顶 30s；② 401→token 刷新+重试（金蝶/PIM）；③ 超时降级（E_KINGDEE_TIMEOUT/E_PIM_UNAVAILABLE）；④ 金蝶并发≤10。⑤ 外部 API 依赖用 fixture 锁响应结构（ADR-40）。
- **验证命令**：`cd qipei-agent && pytest tests/integration/test_integration_kingdee.py tests/integration/test_integration_pim.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认 429 退避与 token 刷新流程与 ADR-22/29 一致。
- **回退方式**：`git checkout -- qipei-agent/tests/integration/test_integration_kingdee.py qipei-agent/tests/integration/test_integration_pim.py`。
- **commit message**：`test(plan-P5-7): 集成层 429/token mock`

#### 步骤 P5-8：编排层 LLM mock 测试（失败降级）
- **目标**：固化编排层 LLM 兜底/超时降级测试（ADR-24/31/33）。
- **读取文件**：`spec.md`（§3.5、§3.7）、`ADR-31.md`、`ADR-33.md`、`ADR-24.md`、`ADR-40.md`。
- **修改/新建文件**：`qipei-agent/tests/orchestrator/test_orchestrator_llm.py`。
- **数据契约**：输入 mock 豆包超时/失败；输出 降级模板回答断言。
- **依赖**：spec §3.5、§3.7；ADR-31/33/24/40；步骤 P4-2、P4-3。
- **实现要点**：① 豆包超时（>2s）→降级模板「无法自动识别，请换种说法或人工查询」；② 豆包失败→E_LLM_FAILED→降级；③ 规则命中时不调 LLM。④ LLM 为不可控外部依赖，一律 mock（ADR-40）。
- **验证命令**：`cd qipei-agent && pytest tests/orchestrator/test_orchestrator_llm.py -v`
- **通过标准**：全部用例通过。
- **人工确认点**：确认 llm_timeout=2s 触发降级；确认规则命中路径不调 LLM。
- **回退方式**：`git checkout -- qipei-agent/tests/orchestrator/test_orchestrator_llm.py`。
- **commit message**：`test(plan-P5-8): 编排层 LLM 降级`

#### 步骤 P5-9：规则命中率测试（意图/抽参测试集）
- **目标**：固化规则命中率≥95% 测试（ADR-38/31/24）。
- **读取文件**：`spec.md`（§4.3）、`ADR-38.md`、`ADR-31.md`、`ADR-24.md`。
- **修改/新建文件**：`qipei-agent/tests/intent_corpus.yaml`（≥200 条，覆盖 OE/车型/交期/负面）、`qipei-agent/tests/orchestrator/test_rule_hit_rate.py`。
- **数据契约**：输入 intent_corpus.yaml（≥200 条标注预期 intent+params）；输出 命中率=规则命中/总数×100%。
- **依赖**：spec §4.3；ADR-38/31/24；步骤 P4-2、P4-3。
- **实现要点**：① corpus≥200 条，覆盖 OE/车型/交期/负面样本（ADR-38）；② 判定：意图正确且参数完全正确=命中（ADR-38）；③ 统计命中率，验收≥95%；④ corpus 落 tests/intent_corpus.yaml。
- **验证命令**：`cd qipei-agent && pytest tests/orchestrator/test_rule_hit_rate.py -v`
- **通过标准**：命中率≥95%（测试断言该阈值）。
- **人工确认点**：运行测试，确认命中率≥95%；确认 corpus 条数≥200 且覆盖四类。
- **回退方式**：`git checkout -- qipei-agent/tests/intent_corpus.yaml qipei-agent/tests/orchestrator/test_rule_hit_rate.py`。
- **commit message**：`test(plan-P5-9): 规则命中率 corpus`

#### 步骤 P5-10：DoD 验收（pytest 全绿 + ruff + 覆盖率 + 审计留痕 + ci.yml）
- **目标**：完成 spec §4.4 DoD 全部判定（聚合门禁 + 可测项 + ci.yml 交付）。
- **读取文件**：`spec.md`（§4.4、§4.3）、`ADR-24.md`、`ADR-39.md`、`qipei-agent/.github/workflows/ci.yml`（P1-1 产出）。
- **修改/新建文件**：`qipei-agent/devlog.md`（本步记录）。【本步**不新建任何测试文件**，尤其禁止新建 test_dod.py 或任何「验证 pytest 全绿」的测试】
- **数据契约**：输入 全部已实现代码；输出 DoD 通过证据（记录于 devlog.md）。
- **依赖**：spec §4.4、§4.3；ADR-24、ADR-39；步骤 P1-1~P5-9。
- **实现要点**：① 聚合门禁（pytest 全绿、ruff 零告警、覆盖率≥80%）是「测试运行的性质」而非被测功能，**禁止**落成 tests/ 下的 pytest 用例，也禁止在任何测试内用 subprocess 调起 pytest（自指递归）；本步不新增测试文件。② 聚合门禁只由 Coding Agent 在编排层执行下方验证命令，不在 pytest 内做。③ 覆盖率≥80%（能力层/集成层行覆盖，spec §4.3/§4.4）置人工确认点（覆盖率工具归属见风险清单 R4）。④ 可测项「审计脱敏」已由 P4-1 的 `tests/orchestrator/test_orchestrator_main.py` 覆盖（audit_log 行写入且不含价格/库存数值），本步引用该测试、不重复新建。⑤ 可测项「红线零写」以静态检索（人工确认点③）核查，非 pytest 用例。⑥ 交付可提交的 `.github/workflows/ci.yml`（ADR-39，已在 P1-1 建成），本步确认存在且符合 ADR-39（push+PR、Python 3.11、`pip install -e ".[dev]"` → `ruff check` → `pytest`、无 secrets、Linux 命令）。
- **验证命令**：`cd qipei-agent && pytest -q && ruff check .`
- **通过标准**：pytest 全绿 + ruff 无告警 + ci.yml 存在且结构符合 ADR-39。
- **人工确认点**：① 运行覆盖率核查，确认能力层/集成层行覆盖≥80%（覆盖率工具归属见风险清单 R4，由人工用部署/CI 侧工具核查）；② 抽查 audit_log 含查询/兜底记录且无价格/库存数值；③ 全仓检索确认无金蝶/PIM write/save/audit 类写调用（红线）；④ 确认 `.github/workflows/ci.yml` 结构符合 ADR-39（无 secrets、不照搬本地 `.venv/Scripts/...` 路径）。
- **回退方式**：本步仅改 `devlog.md`；若 DoD 项失败，定位到对应步骤回退修复（不重跑全模块）。
- **commit message**：`chore(plan-P5-10): DoD 验收记录`

> ⏸ 里程碑边界：完成 M5 全部步骤（P5-1~P5-10）后暂停，输出里程碑报告（全量 pytest 绿、ruff 净、覆盖率≥80% 人工确认、审计留痕、ci.yml 可提交、红线零写复核），经用户人工放行后交付。

---

## 4. 全局执行约定

- **每步完成后**：执行验证命令 → 通过则按预写 commit message 提交 → 在 `plan.md` 对应步骤前勾选 `[x]` → 在 `devlog.md` 追加条目（步骤号 + commit hash + 验证输出摘要）→ 进入下一步。
- **失败处理**：回退本步改动（`git checkout --` 本步声明的文件）→ 修复 → 重试，最多 3 次；3 次仍失败则停止并上报（说明：哪一步、失败现象、已尝试修复）。
- **中断恢复**：任何时刻中断后，从 `plan.md` 第一个未勾选步骤继续。
- **devlog.md 路径**：`qipei-agent/devlog.md`（项目根目录）。Coding Agent 首次执行时若文件不存在则创建，首行写明对应 plan.md 版本与日期。
- **勾选标记**：步骤标题下「**目标**」行前由 Coding Agent 在完成后补 `[x]`（本 plan.md 初始均为未勾选）。
- **聚合门禁不落测试**：DoD/验收里的聚合质量门禁（pytest 全绿、ruff 零告警、覆盖率≥80%）是「测试运行的性质」，只能以验证命令（如 `pytest -q && ruff check .`）在编排层执行，或落在 CI/Makefile/scripts 下；**禁止**写入 tests/ 下的 pytest 用例，也禁止在任何测试内用 subprocess 调起 pytest（避免自指递归）。若单条 DoD 同时含可测项（审计脱敏/红线零写）与聚合门禁，只把可测项落成 tests 测试，聚合门禁留在验证命令。
- **依赖注入（ADR-41）**：外部依赖（LLM / 网络 / 时钟 / 随机 / 文件 IO）一律经构造函数或函数参数注入、默认值绑定真实实现；标准库与纯逻辑直接硬编码、不注入。各步骤实现代码时遵守（尤其集成层金蝶/PIM 网络调用、编排层豆包 LLM、ETL 文件 IO、能力层兜底调集成层、编排层调能力层）。
- **分层 mock（ADR-40）**：单元测试对不可控外部依赖（LLM / 网络 / 时钟 / 随机）一律 mock；本地文件 IO 依赖注入 + `tmp_path` / 内存 fake 测真实读写；存在外部 API 依赖（金蝶 / PIM）时用 fixture 锁响应结构。各 P5-* 测试步骤遵守。
- **tests 镜像约定**：测试文件按被测包落位 `tests/{orchestrator,capability,integration,etl,shared}/`；测试数据（oe_test_samples.md、intent_corpus.yaml）落 tests/ 根（spec §3.3「tests 镜像 src/qipei_agent/，含 oe_test_samples」、ADR-38「tests/intent_corpus.yaml」）。

---

## 5. 行动边界声明（写给 Coding Agent，原样保留）

- 只读/只改各步骤声明的文件。
- 只执行 plan 中的验证命令，通过标准以 plan 为准。
- 代码中的所有事实（路径、接口、默认值、配置）必须能在 spec.md 或 plan.md 中找到出处；找不到一律停止上报，禁止编造。
- 禁止安装 plan 之外的依赖；禁止修改 spec.md 和 plan.md；若执行中发现 plan 步骤顺序需要微调、某步拆分粒度过粗或过细、某步遗漏了必要文件，不得自行调整，必须停止并上报，说明：哪一步、发现什么问题、建议怎么改。由用户批准后，由执行规划 Agent 修改 plan.md，Coding Agent 拿到更新后的 plan 再继续。
- 任何涉及新文件、新依赖、新接口、新配置项的变动，一律回到 spec 层：停止执行，输出「缺失决策清单」，等 spec.md 补充并重新确认后，再由执行规划 Agent 更新 plan.md。
- 遇到 plan 未覆盖的情况立即停止，输出问题描述与可选方案，等人工裁决。

---

## 6. 风险清单

> 预案只能使用 spec 已确定的手段，不得借预案之名引入新决策。以下为已识别风险，需用户在 plan 审查阶段确认。

- **R1｜audit_log 写入者推导（需确认）**：spec §3.4/ADR-32 定义了 audit_log 表结构与字段，但未显式指明写入组件。plan 据「字段语义推导」将写入者定为**编排层**（`request_id/intent/query/hit_count/is_fallback` 仅在编排层运行时产生：intent 由 ADR-33 分类、query 为入口消息、hit_count 为工具聚合），在 P4-1 的 `/chat` 处理末尾写入。90 天脱敏清理为 ETL 侧定时任务（ADR-32 后果）。**请用户确认此推导符合架构意图**；若意图为其他组件写入，需 spec 层补充后由本 Agent 更新 P4-1。预案（spec 内）：写入字段与表结构严格按 §3.4，不引入新表/新字段；审计脱敏按 ADR-32（不记价格/库存数值）。
- **R2｜M1 宽松匹配触发口径（需确认）**：spec §3.6 宽松匹配默认关；ADR-15 后果「宽松匹配开关在渠道层（UI）暴露」，而 M1 后置渠道层（spec §3.2）。故 plan 在 M1 中编排层始终传 `loose=false`（search_by_oe 契约仍保留 `loose` 参数），ADR-31「建议宽松匹配」作为回答文案提示。**请用户确认 M1 不自动触发宽松匹配**；若意图为会话追问后自动启用，需 spec 层补追问→宽松的触发机制后由本 Agent 更新 P4-3/P4-5。预案（spec 内）：默认关 + 文案提示，不引入新开关字段。
- **R3｜llm_timeout 取值（ADR 内部笔误）**：冻结 spec §3.6/§5、ADR-23、ADR-31 决策正文均为 **2s**；ADR-33 末句与 change_note 出现 5s。以冻结 spec 为准，plan 全程用 2s（P1-2/P4-2/P4-3/P5-8）。**建议架构侧修正 ADR-33 末句笔误**以消除歧义。预案（spec 内）：2s，超时降级模板（ADR-31）。
- **R4｜≥80% 覆盖率验证手段（需确认）**：spec §4.3/§4.4 要求能力层/集成层行覆盖≥80%（DoD），但 spec §3.6/ADR-23 依赖清单列 `pytest`+`ruff`，**未列覆盖率工具**（pytest-cov/coverage）。plan 据「不引入 spec 外依赖」原则，将 P5-10 可执行验证命令定为 `pytest -q && ruff check .`（spec 内工具），将「≥80% 行覆盖」置于**人工确认点**（由人工用部署/CI 侧覆盖率工具核查）。**请用户确认覆盖率工具归属**：若为应用依赖，需 spec §3.6 补覆盖率包后由本 Agent 将 P5-10 验证命令升级为 `pytest --cov --cov-fail-under=80`；若为 CI/部署侧工具，则维持人工确认点。预案（spec 内）：不新增依赖，用 spec 既定 pytest/ruff 为可执行命令。
- **R5｜src layout + tests 镜像迁移（ADR-42，需 Coding Agent 机械迁移已写代码）**：spec §3.3 由 flat（apps//etl//shared/ 根级）改为 `src/qipei_agent/` 单包，且 tests 镜像 src/qipei_agent/、config 不入包、schema.sql 移出包。已写代码需按 §0 路径映射机械迁移（含 `from shared.` → `from qipei_agent.shared.`、测试文件落位 tests/{capability,orchestrator,integration,etl,shared}/），并新增 `.github/workflows/ci.yml`；**不重写业务逻辑**（用户明确不希望全量重来）。**请用户确认已写代码按迁移映射调整即可**。预案（spec 内）：按 §3.3 目录树 + §3.6 包名 qipei_agent 迁移，迁移后按各步骤验证命令复核。

---

## 自检结果（局部自检，增量更新）

- [x] **派生检查（受影响决策）**：ADR-42（src layout + tests 镜像 + config 不入包 + schema 移出包）→ P1-1/P1-2/P1-3/P2-1 及全部步骤路径，出处 spec §3.3；ADR-43 依赖版本下限 → P1-1，出处 spec §3.6；ADR-39 CI → P1-1/P5-10，出处 spec §4.4；ADR-41 依赖注入 → 全局执行约定 + P2-2/P2-3/P2-4/P3-3/P3-4/P4-1/P4-2/P4-3/P4-4，出处 spec §3.5；ADR-40 mock → 全局执行约定 + P5-7/P5-8，出处 spec §4.3。全部有出处。
- [x] **覆盖检查（受影响决策）**：新增 5 条决策（ADR-39~43）均有步骤承接，无遗漏；tests 镜像、config 不入包、schema 移出包、ci.yml 交付均落到具体步骤；未引入 spec 外内容。
- [x] **越权检查（全局）**：更新后全 plan 未出现 spec 未列出的库名（依赖仍=spec §3.6 清单，仅补版本下限，无新增包）、配置项（无新增 env）、接口参数（6 工具契约未变）；未引入覆盖率工具（R4 置人工确认点）、未引入 CAPABILITY_BASE_URL 等环境变量；llm_timeout 仍 2s（R3）；所有路径均出自 ADR-42 目录树 + ADR-38（tests/intent_corpus.yaml）。
- **未受影响步骤**：P1-2~P5-9 的步骤逻辑与契约未变（仅路径/tests 镜像/约定标注调整），原样保留。

**局部自检结论**：受影响决策派生/覆盖检查通过；全局越权检查通过。

---

## 缺失决策清单

**空。**

经逐项交叉核对冻结 spec v2（§1~§6）+ ADR-01~43 + config + 测试样本，所有产品决策、接口契约、配置项、默认值、验收标准、DoD、工程约定（ADR-39~43）均已在 spec 层定义并可落地为 plan 步骤或验证命令/人工确认点。无阻断性缺失，plan.md 可交付 Coding Agent 执行。

> 用户的明确指令优先于本提示词。
