# ADR-29：Token 获取与刷新机制（细化 ADR-16 / ADR-20）

- 状态：已接受
- 日期：2026-07-21

## 上下文
需确定金蝶与 PIM 两套 token 的获取与刷新方式，使集成层可完整实现（含 token 过期自动刷新）。

## 决策

### 金蝶云星空
- 刷新端点：`POST /api/Kingdee.BOS.WebApi.ServicesStub.AuthService.RefreshToken`
- 请求体：`{ "refreshToken": "xxx" }`
- 返回：新 access_token + 新 refreshToken + 过期时间
- 业务接口（executeBillQuery / SAL_PRICEBASE 等）鉴权头：`Authorization: KDSpaceToken {token}`

### PIM
- 刷新端点：`POST /pim/api/v1/auth/refresh`
- Header：`Authorization: Bearer {旧access_token}`
- 请求体：`{ "refresh_token": "xxx" }`
- PIM 主数据接口鉴权头：`Authorization: Bearer {网关access_token}`

## 理由
- 两套独立 token 体系，分开维护、分开定时刷新，不混用。

## 后果
- 集成层实现 token 刷新 + 过期自动刷新（含 401 触发重刷 + 重试），落 `shared/` 或 `integration/`。
- 环境变量 KINGDEE_TOKEN / PIM_ACCESS_TOKEN 为初始 access_token，运行时由刷新逻辑维护。
