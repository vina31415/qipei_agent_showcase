# ADR-25：M1 入口与上下文契约

- 状态：已接受
- 日期：2026-07-20

## 上下文
需确定 M1 的对话入口形态、会话与身份传递方式，作为 Plan Agent 的「第一个可交付入口」。

## 决策
1. M1 入口 = 编排层 HTTP/JSON 对话 API（`POST /api/v1/chat`），不做聊天页、不做金蝶/CRM 内嵌 UI；渠道层（消息适配器）M1 不实现、后置。
2. 身份/角色采用「信任调用方」：ERP 侧已完成登录，agent 信任 context 中调用方声明的 user_id/role，不另做登录态校验。
3. 多轮会话状态存 Redis（session_id 维度）。

### 请求 / 响应契约
请求：
```json
{
  "session_id": "可选，首次不传由服务端生成",
  "message": "查 OE 6Q0820803C",
  "context": {
    "user_id": "必填，ERP 侧账号/工号",
    "role": "sales | merchandiser | warehouse | cs（必填）",
    "customer_id": "可选，客户内码 FCUSTID",
    "customer_tier": "可选，客户等级编码",
    "currency": "可选，默认 CNY",
    "quantity": "可选，数量（阶梯价）"
  }
}
```
响应：
```json
{
  "session_id": "...",
  "request_id": "...",
  "intent": "oe_query",
  "answer": { "...结构化回答..." }
}
```

## 理由
- HTTP API only：M1 收窄到核心能力，ERP 侧直接调用即可，渠道层后置不阻塞核心价值。
- 信任调用方：内网内部助手，ERP 已鉴权，避免重复登录体系，泄密面不增。
- Redis：多轮状态跨请求持久、便于水平扩展，优于单实例内存。

## 后果
- orchestrator 直接暴露 `/api/v1/chat`，作为 M1 唯一入口。
- context 中 role 用于权限过滤（ADR-07）；customer_id/tier/quantity/currency 用于价格取数（ADR-26）。
