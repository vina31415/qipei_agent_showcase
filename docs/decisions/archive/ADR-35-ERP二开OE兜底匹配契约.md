# ADR-35：ERP 二开 OE 兜底匹配契约（BD_MATERIAL_OE_EXT）

- 状态：已接受
- 日期：2026-07-22

## 上下文
主检索（PIM → 产品主数据中心）miss 时兜底 OE→SKU，需确定 ERP 二开 OE 检索契约。标准金蝶 BD_MATERIAL 不带 OE 字段，OE 存于二开物料扩展表单。

## 决策
- FormId：`BD_MATERIAL_OE_EXT`（金蝶 BOS 二开表单，依附 FMATERIALID）
- 调用：executeBillQuery，鉴权 KDSpaceToken，limit=20，分页字段 FRowIndex（返回记录数 < limit 即终止）
- 查询字段：`FID / FMATERIALID / FOENO / FOETYPE / FREMARK`
- Filter：`FOENO LIKE '%{oe_input}%'`（单 OE 入参，禁止批量）

### 约束
1. 仅 LIKE 模糊，性能弱，单次单 OE。
2. 返回 FMATERIALID 后关联 BD_MATERIAL 拿 SKU 编码 / 名称。
3. 归一化仍在智能体侧执行，金蝶只做原始字符串模糊匹配，不清洗。
4. 脏数据多，兜底结果降权：**主检索（MySQL，PIM 来源）结果优先 > 金蝶二开 OE 扩展表结果**。兜底只查金蝶，不实时打 PIM（主检索已查过 MySQL）。

## 理由
- 二开扩展表是 OE 在金蝶侧的唯一存储；LIKE 模糊 + 降权，避免脏数据误配。

## 后果
- kingdee.py 封装 BD_MATERIAL_OE_EXT 兜底查询；检索结果合并时 PIM 优先、金蝶兜底靠后并标注「兜底来源」。
