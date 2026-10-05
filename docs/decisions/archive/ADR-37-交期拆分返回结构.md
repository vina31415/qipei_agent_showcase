# ADR-37：交期拆分返回结构

- 状态：已接受
- 日期：2026-07-22

## 上下文
calc_lead_time 涉及现货不足拆分、多笔在途 PO、缺口采购，需明确返回结构（主交期单一值 + 分段明细）。

## 决策
- `lead_time`：**主交期单一值** = 满足本次询价全部数量所需的最晚天数（对客户承诺口径）。
- `split`：分段明细列表，每段 `{segment, qty, lead_time, arrival_date?}`，segment ∈ `{现货, 在途, 采购}`。
- 主交期 = max(各段 lead_time)；需求完全由现货满足时只有一段「现货」。

### 示例（需求 600，现货 100、在途 300、缺口 200）
```json
{
  "sku_code": "...",
  "lead_time": 15,
  "split": [
    {"segment":"现货","qty":100,"lead_time":1},
    {"segment":"在途","qty":300,"lead_time":5,"arrival_date":"2026-10-03"},
    {"segment":"采购","qty":200,"lead_time":15}
  ],
  "supplier_note": "交期取自默认供应商 博世",
  "risk_level": "medium",
  "risk_hint": "缺口 200 件需现采，非默认供应商供货",
  "pos": [{"supplier":"博世","arrival_date":"2026-10-03","qty":300}],
  "alternatives": [{"supplier":"德尔福","lead_time":12}]
}
```

## 理由
- 主交期单一值便于业务员直接承诺；split 明细暴露缺口与分段，符合 ADR-27 拆分规则。

## 后果
- 修正 ADR-34 calc_lead_time 响应 schema；answer_render 按 split 渲染分段。
