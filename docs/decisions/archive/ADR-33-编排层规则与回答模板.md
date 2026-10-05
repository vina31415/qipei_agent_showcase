# ADR-33：编排层规则与回答模板（附录）

- 状态：已接受
- 日期：2026-07-21

## 上下文
需把编排层「自研轻量编排」落到可编码：意图列表、参数抽取规则、追问条件、工具调度顺序、回答模板、多轮状态存储。

## 决策

### 意图列表（M1 四种）
1. `oe_query`：OE 号 → SKU
2. `fitment_query`：车型 → SKU
3. `lead_time_query`：SKU 交期查询
4. `composite_query`：OE/车型 → SKU → 库存/价格/交期（一步到位，默认意图）

### 参数抽取规则（规则优先）
| 参数 | 规则（正则/关键词） | 优先级 |
|---|---|---|
| OE 号 | `[A-Z0-9][A-Z0-9\s\-\.\/]{3,}` 且命中已知 OE 前缀/分隔符模式 | 高 |
| 品牌 | brand 词典匹配（brand_normalize.yaml 的 key） | 高 |
| 车系 series | 车型短语中「品牌后第一词」 | 中 |
| 车型 model | 品牌/车系后的型号词（如 `GOLF IV`） | 中 |
| 年份 year | `19\d{2}|20\d{2}` 四位数字 | 高 |
| 数量 quantity | `\d+\s*(件|套|只|个)` | 中 |

规则 miss 时降级豆包 function calling（`llm_timeout` 5s）。

### 追问条件
| 场景 | 动作 |
|---|---|
| 车型缺 year | 追问「请补充年份」 |
| OE 无结果 | 提示未找到 → 触发兜底 → 仍无 → 建议宽松匹配或换车型 |
| 车型缺 series/model | 追问补全（series 为二级过滤必需） |
| 多 SKU 命中 | 不追问，直接返回排序列表 |
| 组合查询参数不全 | 缺啥追问啥，最多追问 2 轮 |

### 工具调度顺序
- `oe_query`：normalize_oe → search_by_oe →（composite 时）get_stock → get_price → calc_lead_time
- `fitment_query`：search_by_fitment →（composite 时）get_stock → get_price → calc_lead_time
- `lead_time_query`：calc_lead_time

### 回答模板（answer_render，模板拼接，不调 LLM）
```
[命中] 共 {N} 个匹配 SKU：
1. {sku_code} {name} [{原厂OE/REF参考号}]
   适配：{brand} {series} {model}（{year_start}-{year_end}）
   {图片}
   库存：{on_hand}（现货）| 交期：{lead_time}
   价格：{price} {currency}（含税）
   {risk_level 时} ⚠ {risk_hint}
[未命中] 未找到匹配，已尝试兜底；建议宽松匹配或换车型查询。
```

### 多轮状态（Redis）
- key：`session:{session_id}`
- value：`{intent, params, last_query, history:[...最多10条]}`
- TTL：30 分钟（闲置过期）

## 理由
- 规则优先保证命中率≥95% 与速度；LLM 仅兜底。
- 模板回答避免敏感数据出网（ADR-13）。

## 后果
- `intent.py`/`param_extract.py`/`tool_dispatch.py`/`answer_render.py` 按此实现。
- Redis 会话结构落 `shared/` 常量，TTL 30min。
