# 汽配售后业务智能体 开发规格（spec.md）

> 本文档为决策冻结文档，由架构设计 Agent 与用户讨论生成，用户已审核确认，文档中无任何未确认项。
> **本文档 + 附件 ADR-01~43.md + config/*.yaml + 测试样本 构成完整冻结输入**（ADR-38 = 规则命中率判定与意图/抽参测试集，配套 §4.3；ADR-39~43 = 默认工程约定，配套 §3.3/§3.5/§3.6/§4.3/§4.4）；执行规划 Agent 与 Coding Agent 只能依据此完整输入行动，不得引入本文档之外的任何决策。
> 每条决策括注 ADR 编号，决策理由见对应 ADR-xx.md。

## 1. 项目概述与目标

为 B2B 汽配售后工贸工厂打造企业级业务智能体，对内服务四类角色：**业务员、跟单员、仓库、售后客服**（ADR-01）。

智能体定位「内部助手」——夹在「人」和「系统」之间，**不直接面对客户、不对外暴露**（ADR-01）。

第一里程碑聚焦：**对话式 OE 号查询 + 车型查询**，附带库存、分级价、交期（ADR-01）。

**成功标准（ADR-09、ADR-31）**：
1. OE 检索命中率 **≥98%**（端到端，含 ERP 兜底）
2. 「OE → 库存 → 价格 → 交期」多步收敛为 **1 轮对话**
3. 端到端查询响应 **P95 ≤3 秒**（前提：规则命中率 ≥95%）
4. 参数抽取**规则命中率 ≥95%**（判定口径见 ADR-38）
5. 红线：交期 / 下单**零自动落库**，100% 由人确认

## 2. 产品决策

### 2.1 目标与场景
- 目标用户：业务员 / 跟单员 / 售后客服 / 仓库（ADR-01）
- 核心痛点：OE 号格式不一导致检索漏/错（现状约 70%）；多步人工操作（ADR-01、ADR-09）

### 2.2 范围内功能（In Scope）
1. **OE 号 → SKU**（附适配车型、图片、库存、分级价、交期）
2. **车型（brand/series/model/year）→ OE / SKU**
3. **交期计算**（现货/在途/采购周期组合 + 插单风险提示，人确认）

### 2.3 范围外功能（Out of Scope）
VIN、报价单草稿、对外渠道（WhatsApp，ADR-18）、RAG（ADR-03）、汇率换算（ADR-26）、任何全自动写操作（ADR-06）。

### 2.4 优先级
MVP（M1）= 上述三项；后续 = VIN、报价草稿、对外渠道、RAG、汇率。

## 3. 技术决策

### 3.1 技术栈
Python 3.11 / FastAPI / 豆包 / 自研编排 / MySQL 8.0 / Redis（ADR-03、ADR-08、ADR-10、ADR-25）。

### 3.2 架构与模块（ADR-02、ADR-04）
五层 + 数据地基：渠道层（M1 后置）→ 编排层（云侧 orchestrator）→ 能力层（内网 capability）→ 集成层（kingdee/pim）→ 横切层 + 产品主数据中心（MySQL）。**主路径不实时打金蝶/PIM**（金蝶/PIM 只在 ETL 触发；金蝶额外在兜底触发，ADR-31）。

### 3.3 目录结构（ADR-14、ADR-42）
src layout，构建后端 hatchling，包名 `qipei_agent`（= project_name `qipei-agent` 连字符转下划线）：
```
qipei-agent/
├── src/qipei_agent/
│   ├── orchestrator/    # 云侧：main/intent/param_extract/tool_dispatch/answer_render
│   ├── capability/      # 内网侧：main + oe_search/fitment_search/stock/price/lead_time
│   ├── integration/     # 内网侧：kingdee.py / pim.py（含 token 刷新）
│   ├── etl/             # extract/normalize_oe/normalize_fitment/load
│   └── shared/          # models/config/permissions
├── config/              # oe_normalize/brand_normalize/customer_level/permission/app.yaml（部署期配置，不入包）
├── tests/               # 镜像 src/qipei_agent/，含 oe_test_samples
├── deploy/{internal,cloud}/
├── .github/workflows/ci.yml   # 见 §4.4（ADR-39）
└── pyproject.toml       # hatchling 构建后端；[project.optional-dependencies] dev = pytest/ruff
```

### 3.4 数据模型与数据流
ETL：PIM + 金蝶 → 清洗归一化 → 产品主数据中心（MySQL）→ 能力层检索 → 模板回答。库存/在途 5min 增量、价格 1h 全量、主数据/交期参数每日全量（ADR-32）。

| 表 | 关键字段 | 说明 |
|---|---|---|
| `product` | sku_code, name, spec, image_url, material_group, is_sellable, lead_time_override, procurement_cycle | SKU + 现货交期覆盖 + 采购周期 FLEADTIME |
| `customer` | customer_id, name, customer_tier, currency | 客户主数据（ETL 自 BD_CUSTOMER + BD_CUSTLEVEL） |
| `oe_mapping` | sku_code, oe_normalized, oe_raw, oe_base, oe_type | OE 映射 |
| `fitment` | sku_code, brand, series, model, engine_code, year_start, year_end, chassis_code, note | 车型适配 |
| `stock` | sku_code, on_hand | 现货 FAVAILABLEQTY |
| `purchase_order` | sku_code, supplier_id, plan_arrival_date, not_receive_qty | 在途 PO |
| `supplier_material` | sku_code, supplier_id, is_default, lead_time_supp | 供应商维度交期 |
| `supplier_month_max` | sku_code, supplier_id, max_month_qty | 历史月最大供货量（ETL 自 V_MATERIAL_SUPPLIER_MONTH_MAX_QTY） |
| `price` | sku_code, customer_id, customer_tier, price, qty_low, qty_high, is_include_tax, tax_rate, currency | 分级价（SAL_PRICEBASE） |
| `audit_log` | request_id, user_id, role, intent, query, hit_count, is_fallback, created_at | 审计（脱敏，90 天） |

历史月最大供货量经 ETL 同步到 `supplier_month_max` 表（每日全量，ADR-36）。

### 3.5 接口契约

#### 依赖注入编码约束（ADR-41）
外部依赖（LLM / 网络 / 时钟 / 随机 / 文件 IO）一律经构造函数或函数参数注入、默认值绑定真实实现；标准库与纯逻辑直接硬编码、不注入。

#### 入口契约（ADR-25）
`POST /api/v1/chat`，信任调用方，Redis 会话（TTL 30min）：
```json
请求 { "session_id":"可选", "message":"查 OE 6Q0820803C", "context":{"user_id","role","customer_id?","currency?","quantity?"} }
响应 { "session_id","request_id","intent","answer":{...} }
```

#### 能力层工具 HTTP（ADR-30、ADR-34）
统一端点 `POST /api/v1/tools/{tool}`，Header `X-Request-Id`，信封 `{request_id, ok, data|error{code,message}}`。**请求 body 均含 `user_id` + `role`（权限过滤在能力层，非编排层）**：

| 工具 | 端点 | 请求 body（+user_id,role） | data 响应 |
|---|---|---|---|
| normalize_oe | `/tools/normalize_oe` | `{oe_raw}` | `{oe_normalized, is_valid}` |
| search_by_oe | `/tools/search_by_oe` | `{oe_normalized, loose}` | `{skus:[{sku_code,name,oe_raw,oe_type,label,image_url,fitments}]}` |
| search_by_fitment | `/tools/search_by_fitment` | `{brand, series, model, year}` | `{skus:[{sku_code,name,oe_list,image_url}]}` |
| get_stock | `/tools/get_stock` | `{sku_code}` | `{sku_code, on_hand}` |
| get_price | `/tools/get_price` | `{sku_code, customer_id, quantity}` | `{price, tax_included, original_price, currency, customer_tier, price_type, qty_range}` |
| calc_lead_time | `/tools/calc_lead_time` | `{sku_code, quantity}` | `{lead_time, split:[...], supplier_note, risk_level, risk_hint, pos, alternatives}`（split 分段见 ADR-37） |

#### 集成层外部接口
| 接口 | 来源 | 关键契约 | ADR |
|---|---|---|---|
| executeBillQuery | 金蝶 | BD_MATERIAL（KDSpaceToken） | ADR-16 |
| 价格本 | 金蝶 | SAL_PRICEBASE（FCUSTLEVELID/FQTYLOW/FQTYHIGH/FPRICE/FISINCLUDETAX/FTAXRATE/FCURRENCYID） | ADR-26 |
| 客户主数据 | 金蝶 | BD_CUSTOMER（FCUSTID/FCUSTLEVELID/FCURRENCYID） | ADR-26 |
| 供应商关联 | 金蝶 | BD_MATERIALSUPPLIER（FISDEFAULTSUPPLIER/FLEADTIMESUPP） | ADR-27 |
| 采购订单（在途） | PIM/金蝶 | PIM PO：FPLANARRIVALDATE/FNOTRECEIVEQTY；金蝶 PUR_PURCHASEORDER：FQTY/FRECEIVEQTY/FDOCUMENTSTATUS（未收=FQTY-FRECEIVEQTY） | ADR-17、ADR-27 |
| OE 兜底检索 | 金蝶二开 | BD_MATERIAL_OE_EXT（FOENO LIKE 模糊） | ADR-35 |
| 历史供货量 | 金蝶视图 | V_MATERIAL_SUPPLIER_MONTH_MAX_QTY | ADR-36 |
| OE/车型主数据 | PIM | GET /api/pim/adapt/oe-vehicle（Bearer） | ADR-20 |
| Token 刷新 | 金蝶/PIM | /AuthService.RefreshToken；/pim/api/v1/auth/refresh | ADR-29 |

#### OE 归一化规则（ADR-15 v3）
流水线：trim → 大写 → 去前缀（大写清单、长度降序、边界规则）→ 去非字母数字 → 纯数字去前导零 → 全 0 标记无效。

前缀清单（大写，含标点边界）：`REF.NO.` / `OEM` / `OE` / `REF` / `NO.` / `N°` / `OE#` / `OEM#`
- 无标点后缀前缀（`OE`/`OEM`/`REF`）匹配后必须紧跟非字母数字或字符串结尾（防 `OEM123` 误删）；含标点前缀自带边界。

检索两模式：精确（默认）+ 宽松（剥离末尾连续字母，必标「非精确」）。多 SKU：原厂 OE 优先、REF 靠后、sku_code 升序，带【原厂 OE】【REF 参考号】标签。

#### 编排规则（ADR-33）
意图 4 种（oe_query / fitment_query / lead_time_query / composite_query）；参数抽取规则优先（正则 + 词典），miss 降级豆包（llm_timeout 2s，超时降级模板）；追问条件（缺 year/series/model、OE 无结果）；工具顺序 OE→SKU→库存→价格→交期；回答模板固定结构；Redis 会话 `session:{id}` TTL 30min。

#### 交期规则（ADR-17、ADR-27）
```
交期 = 有现货 ? 现货交期(默认1天) :（有在途 ? 在途交期 : 采购周期(FLEADTIME,兜底15天) + 供应商交期）
```
- 现货不足拆分：现货部分按 1 天，缺口走「在途→采购」；多笔在途 PO 按 FPLANARRIVALDATE 升序取最早，数量不足拆分
- 供应商交期：默认供应商（FISDEFAULTSUPPLIER=1）优先；无默认取最短+标注
- 插单风险：非默认→medium；需求量>supplier_month_max.max_month_qty（ETL 自 V_MATERIAL_SUPPLIER_MONTH_MAX_QTY）→high；>30天→长周期；新供应商/物料无历史→medium+提示
- 红线：交期采纳权在人（ADR-06）

#### 价格取数（ADR-26）
customer_tier：BD_CUSTOMER.FCUSTLEVELID → BD_CUSTLEVEL.FNAME → customer_level.yaml → A/B/C/D（能力层读 MySQL `customer` 表取 tier，**不实时打金蝶 BD_CUSTOMER**）；命中优先级：客户专属价 > 等级价 > 人工询价；阶梯 FQTYLOW~FQTYHIGH（超上限取最大+提示）；含税 FISINCLUDETAX（对外统一含税）；币种以 price 表命中行 currency 为准（=客户主单币种，不做换算）。**无 customer_id 时跳过价格：编排层不调 get_price，回答价格位标注「未提供客户，无法报价」。**

#### ERP 兜底（ADR-28、ADR-35）
触发=search_by_oe / search_by_fitment 检索 miss（get_stock/get_price/calc_lead_time miss 不兜底，直接返回错误）；执行=集成层；OE→SKU 经 BD_MATERIAL_OE_EXT（LIKE 模糊，单 OE，降权）；数据经 BD_MATERIAL/BD_CUSTOMER/BD_MATERIALSUPPLIER/PUR_PURCHASEORDER/SAL_PRICEBASE（limit=20）。兜底查询集合**只查金蝶**（BD_MATERIAL_OE_EXT + 关联物料/客户/供应商/PO/价格表，**不实时打 PIM**）；主检索（MySQL，PIM 来源）结果优先、金蝶兜底靠后并标注，耗时计入 P95。

### 3.6 依赖清单与配置项（ADR-23、ADR-22、ADR-31）
依赖（版本下限，ADR-43）：`fastapi>=0.110 / uvicorn>=0.29 / pydantic>=2.6,<3 / httpx>=0.27 / sqlalchemy>=2.0,<3 / pymysql>=1.1 / volcengine>=1.0 / pydantic-settings>=2.2 / redis>=5.0 / pytest>=8.0 / ruff>=0.4`。

环境变量（必填）：`KINGDEE_BASE_URL/KINGDEE_TOKEN/KINGDEE_REFRESH_TOKEN/PIM_BASE_URL/PIM_ACCESS_TOKEN/PIM_REFRESH_TOKEN/DOUBAO_API_KEY/DOUBAO_MODEL/MYSQL_*/REDIS_URL`。

业务配置默认值：现货交期=1天、采购周期兜底=15天、宽松匹配=关、去前导零=开、connect_timeout=5s、read_timeout=10s、max_retries=3、429读Retry-After、backoff=1s×2封顶30s、sync_concurrency=5、llm_timeout=**2s**（超时降级模板回答）。

### 3.7 错误处理与日志（ADR-22）
结构化 JSON + request_id 贯穿全链路；集成层重试（3次指数退避，429必退避）→降级；能力层结构化 error；编排层 LLM 失败降级规则；主检索 miss → ERP 兜底。错误码：`E_KINGDEE_TIMEOUT/E_PIM_UNAVAILABLE/E_NOT_FOUND/E_LLM_FAILED/E_RATE_LIMIT`。

## 4. 验收决策（ADR-24）

### 4.1 功能验收标准
OE 检索 ≥98%端到端；OE 归一化 26 样本+变体；车型 brand+series+model+year；库存 FAVAILABLEQTY；分级价优先级/阶梯/含税；交期三分支+多笔拆分+risk；权限按 ADR-07 矩阵；零写操作；P95≤3s（规则命中率≥95%）。

### 4.2 性能指标
2.3 万 SKU / OE 映射十万行级；日均 1900–2400、峰值 3200；并发 10–25；OE 查询毫秒级；规则命中率≥95%；审计留痕。

### 4.3 测试要求
pytest，能力层/集成层行覆盖 ≥80%。必测：OE 归一化（26样本+变体+全0）、brand 归一化、检索命中/未命中/兜底、交期三分支+多笔PO+供应商+risk、价格优先级/阶梯/含税、权限过滤、集成层 mock（429/token刷新）、编排层 LLM mock（失败降级）、规则命中率统计（判定口径见 ADR-38）。

分层 mock 策略（ADR-40）：单元测试对不可控外部依赖（LLM / 网络 / 时钟 / 随机）一律 mock；本地文件 IO 依赖注入 + `tmp_path` / 内存 fake 测真实读写；存在外部 API 依赖（金蝶 / PIM）时用 fixture 锁响应结构。

### 4.4 DoD
代码完成 + pytest 全绿（≥80%）+ ruff 无告警 + 关键操作审计留痕 + 交付可提交的 `.github/workflows/ci.yml`（ADR-39）。

CI 约定（ADR-39）：触发 push + PR；Python 单版本 = 3.11（§3.1）；步骤 `pip install -e ".[dev]"` → `ruff check` → `pytest`；无 secrets（不引用 `${{ secrets.XXX }}`）；Linux 标准命令（不照搬本地 `.venv/Scripts/...` 路径）。

## 5. 关键数据与约定汇总（速查表）

| 类别 | 约定值 |
|---|---|
| 成功标准 | 命中率≥98%端到端；规则命中率≥95%；P95≤3s；1轮对话；零落库 |
| 技术栈 | Python 3.11/FastAPI/豆包/自研编排/MySQL 8.0/Redis |
| 入口 | POST /api/v1/chat，信任调用方，Redis 会话 TTL 30min |
| 能力层 | POST /api/v1/tools/{tool}，6 工具，请求含 user_id+role，权限过滤在能力层 |
| 部署 | 数据内网+应用云+反向隧道；主路径不实时打金蝶/PIM；兜底实时打金蝶（不打 PIM） |
| LLM 边界 | 只做意图/抽参/工具选择；回答模板化；敏感数据不出网；llm_timeout 2s（超时降级模板） |
| 金蝶鉴权 | KDSpaceToken；刷新 /AuthService.RefreshToken；并发≤10，429 |
| PIM 鉴权 | Bearer；刷新 /pim/api/v1/auth/refresh |
| 价格本 FormId | SAL_PRICEBASE（非 BD_PriceBase） |
| 数量字段 | FQTYLOW/FQTYHIGH（非 FQTYMIN/MAX） |
| 客户等级字段 | FCUSTLEVELID（关联 BD_CUSTLEVEL） |
| 价格优先级 | 客户专属价 > 客户等级价 > 人工询价 |
| 含税 | FISINCLUDETAX；对外统一含税 |
| OE 前缀（8，大写） | REF.NO. OEM OE REF NO. N° OE# OEM#（长度降序+边界） |
| OE 归一化 | 大写→去前缀→去非字母数字→纯数字去前导零；全0无效 |
| 检索模式 | 精确 + 宽松（剥离末尾字母，必标注） |
| 多 SKU 排序 | 原厂 OE 优先，REF 靠后，sku_code 升序 |
| 现货交期 | 1 天（物料可覆盖） |
| 采购周期兜底 | 15 天 |
| 供应商交期 | 默认供应商优先；无默认取最短+标注 |
| 插单风险 | 非默认→medium；超历史供货→high；>30天→长周期 |
| 在途数量 | 主路径 PIM PO `FNOTRECEIVEQTY`（直接字段，PIM 侧已过滤）；兜底金蝶 `FQTY - FRECEIVEQTY`（计算，筛选 FDOCUMENTSTATUS=C） |
| OE 兜底 | BD_MATERIAL_OE_EXT，FOENO LIKE 模糊；兜底只查金蝶，主检索（PIM 来源）优先、金蝶兜底靠后并标注 |
| 历史供货量 | V_MATERIAL_SUPPLIER_MONTH_MAX_QTY（近12月月度最大入库） |
| ETL 频率 | 库存/在途 5min 增量；价格 1h 全量；主数据/交期参数每日全量 |
| 审计 | audit_log 脱敏（不记价格/库存数值），保留 90 天 |
| 集成重试 | max_retries 3 / backoff 1s×2 封顶 30s / 429 读 Retry-After |
| 集成超时 | connect 5s / read 10s；LLM 2s（超时降级模板） |
| 权限 | 业务员/跟单全量；售后无供应商备注/备选交期；仓库无价格/交期/供应商 |
| 错误码 | E_KINGDEE_TIMEOUT/E_PIM_UNAVAILABLE/E_NOT_FOUND/E_LLM_FAILED/E_RATE_LIMIT |
| DoD | pytest 全绿(≥80%) + ruff 无告警 + 审计留痕 + 可提交 ci.yml |
| 目录结构 | src/qipei_agent/ 单包 + hatchling；tests 镜像 src；config 不入包 |
| CI | .github/workflows/ci.yml：push+PR、Python 3.11、pip install -e ".[dev]" → ruff check → pytest、无 secrets、Linux 命令 |
| 依赖注入 | 外部依赖（LLM/网络/时钟/随机/文件 IO）参数注入、默认绑真实实现；标准库/纯逻辑硬编码 |
| mock 策略 | 不可控外部依赖 mock；文件 IO 注入 + tmp_path；外部 API fixture 锁结构 |
| 依赖版本 | fastapi>=0.110 等主/次版本下限（详见 §3.6，ADR-43） |

## 6. 非目标与约束
- 不对外、不直接面对客户；对外渠道（WhatsApp）后置（ADR-01、ADR-18）
- 不做 RAG / 向量检索（ADR-03）；不做汇率换算（ADR-26）；不做全自动写操作（ADR-06）
- 纯内网备选触发时，豆包替换为私有化 LLM（ADR-11）
- 敏感数据（价格/报价/交期成本/供应商备注）不出网到 LLM、不对仓库开放；库存对仓库开放（ADR-13、ADR-07）
