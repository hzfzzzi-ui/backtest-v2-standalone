## ADDED Requirements

### Requirement: 主系统必须提供持仓感知的 semi-auto reconcile surface
系统 MUST 在 runtime boundary 中提供面向半自动交易链路的 `PositionAwareReconcileSurface`。该 surface SHALL 至少包含：
- `strategy_source`
- `account_id`
- `holding_sync`
- `snapshot_id`
- `reconcile_id`
- `as_of_date`
- `positions`
- `action_sheet`
- `freshness`
- `risk_flags`

该 surface MUST 与现有 experiment surface / execution preview 分层，而 SHALL NOT 由客户端自行把多个底层产物临时拼接成真相。

#### Scenario: 手机端读取最新动作单真相
- **WHEN** 手机端请求半自动交易所需的聚合结果
- **THEN** 后端 MUST 返回 `PositionAwareReconcileSurface`
- **THEN** 客户端 SHALL 能直接读取当前持仓、动作单和 freshness，而不必自己拼接实验成交和 preview 差集

#### Scenario: reconcile surface 不可用时显式返回降级状态
- **WHEN** 最新持仓快照缺失、最新 reconcile run 失败，或当前仍处于 experiment fallback 模式
- **THEN** surface MUST 显式返回 `status` / `source_mode` / `warnings`
- **THEN** 客户端 SHALL NOT 把缺失 surface 误判为“当前无动作”

### Requirement: reconcile surface 必须携带并发校验令牌
系统 MUST 在 reconcile surface 和移动端动作卡中返回足以做并发校验的令牌，至少包括 `snapshot_id`、`reconcile_id` 和 `as_of_date`。任何确认请求若引用的令牌已落后于系统最新有效 surface，服务端 MUST 拒绝该请求。

#### Scenario: 用户确认基于旧 snapshot 的动作卡
- **WHEN** 用户准备确认某张动作卡，但系统最新有效 `snapshot_id` 或 `reconcile_id` 已变化
- **THEN** 服务端 MUST 返回冲突状态
- **THEN** 客户端 SHALL 提示用户先刷新动作单再确认

#### Scenario: 当前版本仍处于 experiment fallback
- **WHEN** 聚合接口返回 `source_mode=experiment_fallback`
- **THEN** 服务端 SHALL NOT 生成可用于真实持仓确认的并发令牌
- **THEN** 客户端 SHALL 显式提示该模式仅供只读参考
