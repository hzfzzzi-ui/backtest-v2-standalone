# api-shared-helper-surface Specification

## Purpose
TBD - created by archiving change cleanup-remaining-architecture-debt. Update Purpose after archive.
## Requirements
### Requirement: 新 API 边界必须依赖独立 shared helper surface
系统 MUST 将新 `backend/api/backtest_v2/*` 与 `backend/api/mobile/*` 复用的 helper 统一放入独立的 `backend/api/shared/*`。新 API 实现 SHALL NOT 继续直接 import `backend/api/endpoints/*` 下的 helper 模块。

#### Scenario: backtest_v2 route 调用共享 helper
- **WHEN** `backend/api/backtest_v2/*` 需要复用路径、状态或 job helper
- **THEN** 实现 MUST 从 `backend/api/shared/*` 导入
- **THEN** 实现 SHALL NOT 直接依赖 `backend/api/endpoints/_paths.py`、`_utils.py`、`_job_store.py` 等历史 helper

#### Scenario: mobile impl 调用 access gate
- **WHEN** `backend/api/mobile/*` 需要复用访问控制或 session gate
- **THEN** 实现 MUST 通过 shared helper surface 获取能力
- **THEN** `backend/api/mobile/*` SHALL NOT 直接锚定在历史 `endpoints` 目录上

### Requirement: 历史 endpoints 目录不得继续承载新 API 的真实宿主实现
系统 MUST 将 `backend/api/endpoints/*` 限制为极少量过渡资源或彻底退场。新 API 主路径 SHALL NOT 通过 `endpoints` 目录承载核心业务实现或共享基础设施。

#### Scenario: 删除旧 helper 目录中的重实现
- **WHEN** shared helper surface 已稳定接管某类通用能力
- **THEN** 相应历史 `endpoints` helper MUST 被删除或退化为非主路径资产
- **THEN** 新 API 路由和 impl MUST 保持物理结构上的自洽

