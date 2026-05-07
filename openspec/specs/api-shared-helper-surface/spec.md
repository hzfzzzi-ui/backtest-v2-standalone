# api-shared-helper-surface Specification

## Purpose

定义 `backend/api/shared/*` 作为当前 API 共享 helper 的正式宿主边界。

## Requirements

### Requirement: 新 API 边界 MUST 依赖独立 shared helper surface

系统 MUST 将 `backend/api/backtest_v2/*` 与 `backend/api/mobile/*` 复用的 helper 统一收敛到 `backend/api/shared/*`。

#### Scenario: backtest_v2 route 调用共享 helper
- **WHEN** `backend/api/backtest_v2/*` 需要复用路径、状态或 job helper
- **THEN** 实现从 `backend/api/shared/*` 导入

#### Scenario: mobile impl 调用共享 helper
- **WHEN** `backend/api/mobile/*` 需要复用访问控制或 session gate
- **THEN** 实现通过 shared helper surface 获取能力

### Requirement: 非主目录 MUST NOT 承载当前 API 主实现

系统 SHALL NOT 通过非主目录承载当前 API 核心业务实现或共享基础设施。

#### Scenario: 审查 API 主实现位置
- **WHEN** 检查当前 API 路由和实现宿主
- **THEN** 主实现位于 `backend/api/backtest_v2/*`、`backend/api/mobile/*` 与 `backend/api/shared/*`
