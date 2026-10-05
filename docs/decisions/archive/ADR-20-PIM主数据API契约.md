# ADR-20：PIM 主数据 API 契约（OE / 车型）

- 状态：已接受
- 日期：2026-07-17

## 上下文
需确定 OE / 车型主数据的 PIM 拉取契约与归一化策略。

## 决策
1. OE / 车型主数据来自 PIM REST API：`GET /api/pim/adapt/oe-vehicle`
2. 鉴权：`Authorization: Bearer {网关access_token}`（PIM 自研网关，与金蝶 KDSpaceToken 独立）
3. 参数：page(默认1) / pageSize(上限500) / materialCode(可选,精准) / oeNo(可选,模糊)
4. 返回（records[]）：
   - 物料：pimId / materialCode / productCategory / updateTime
   - oeList[]：oeRaw / oeNormalized / oeBrand / oeRemark（区分原厂件 OE / REF）
   - vehicleAdaptList[]：brand / series / model / engineCode / yearStart / yearEnd / chassisCode / note
5. ETL 批量拉全量 + 按 OE 单条检索两用。

### OE 归一化策略（重归一化）
- ETL 以 `oeRaw` 按 ADR-15 规则自行重归一化，作为 `oe_normalized` 唯一权威值。
- PIM 的 `oeNormalized` 仅作对账参考：ETL 对比「我方归一化」vs「PIM 归一化」，不一致时告警排查。
- `oe_type` 由 `oeRemark` 映射：含「REF」→ REF，否则 → 原厂。

## 理由
- 归一化规则（前缀清单/分隔符/去前导零）必须可配置、可测试，不押注 PIM 黑盒；98% 命中率责任在己方。
- 车型数据已是结构化字段，无需解析脏文本，仅需字段值标准化。

## 后果
- 产品主数据中心 ETL：拉 PIM → 清洗（OE 重归一化 + 车型字段标准化）→ 落 product / oe_mapping / fitment。
- fitment 表字段对齐 PIM 实际结构（brand/series/model/engineCode/yearStart/yearEnd/chassisCode），取代原 spec §8 的 make/model/year/engine。
- ETL 对账任务产生「归一化不一致」告警，供数据治理。

## 待确认
- 网关 access_token 的获取方式与有效期（沿用业务方原信息：网关认证 AppKey/AppSecret，有效期 2 小时；联调时复核）。
