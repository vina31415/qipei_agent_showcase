# ADR-21：车型实体标准化（fitment 字段 + brand 归一化）

- 状态：已接受
- 日期：2026-07-17

## 上下文
PIM 车型适配已是结构化字段，但 brand 存在缩写/中文/英文混录，需确定字段标准化与归一化规则。

## 决策
1. `fitment` 表字段对齐 PIM 实际结构：`sku_code, brand, series, model, engine_code, year_start, year_end, chassis_code, note`。
2. `engine_code` 统一大写 + 去空格（`aum` → `AUM`）。
3. `year_start` / `year_end` 原样保留，检索时判断 `year ∈ [year_start, year_end]`。
4. `brand` 存在混录（VW / 大众 / Volkswagen），建 `brand_normalize.yaml` 归一到标准编码。
5. 车型检索 `search_by_fitment(brand, series, model, year)`：brand 精确匹配（经映射）+ **series 精确匹配（二级条件，必须）** + model 精确匹配 + year 落区间；engine_code 可选过滤。
   - model 精确匹配：忽略大小写、剔除前后空格、中间多余空格压缩；不做模糊 like。
   - series 必须参与过滤：先匹配 series 车系，再匹配 model（避免不同车系同名 model 乱匹配，如 Series=GOLF / Model=GOLF IV）。
   - 不用模糊检索：车型数据量大，模糊易串款错配，适配错误属重大业务事故。

## 理由
- PIM brand 混录（缩写 / 中文全称 / 英文全称）会导致同车系检索漏配，必须归一。
- 车型数据已是结构化，无需解析文本，仅字段值标准化。

## 后果
- fitment 表取代 spec §8 原 make/model/year/engine 结构。
- `brand_normalize.yaml` 落配置；映射内容在 ETL 阶段从 PIM 去重后的 brand 值 + 业务确认生成，可持续补充别名。
