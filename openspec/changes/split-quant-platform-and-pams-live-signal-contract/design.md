## Context

当前存在两个本地系统：

- `backtest_V2_standalone`：当前承载 A 股研究、baseline、实验产物、移动端审批、模拟账户、持仓感知 reconcile 和 action sheet。
- `pams`：当前承载个人资产管理、账户/持仓/交易流水、通知、Telegram、调度器，同时保留旧策略扫描、旧回测和复制版 `backtest_V2` 草稿。

目标方向已经调整为双系统协同：

- `backtest_V2_standalone` 演进为专业量化研究平台。
- `pams` 演进为个人资产管理系统。
- 正在实盘的策略每日向 PAMS app/web 推送仓位调整信息。

本设计只定义架构边界与第一版跨系统合同，不直接改动策略收益逻辑、baseline 主逻辑、信号时点或成交时点。

## Goals / Non-Goals

**Goals:**

- 明确两个系统的长期职责、数据真值和禁止越界规则。
- 定义 `daily_position_adjustment_package@1` 作为研究平台到 PAMS 的唯一正式 live 调仓合同。
- 定义 live strategy 发布门禁，确保 research-only、shadow、AB 实验不能进入实盘通知流。
- 定义 PAMS 接收、校验、入库、通知、审批和交易生命周期映射边界。
- 给出现有过渡链路的冻结和迁移路径。

**Non-Goals:**

- 不修改当前 baseline、策略排序主因子、股票池/ETF 池、benchmark/regime、信号时点或成交时点。
- 不在 PAMS 内继续实现研究策略、回测引擎或选股逻辑。
- 不直接接券商下单，不定义券商 API 适配。
- 不把 Codex automation 作为生产调仓推送运行时。
- 不把 `outputs/` 文件路径定义为两个系统的长期 API。

## Decisions

### Decision 1: 以系统职责划分真值边界

量化研究平台 owns 研究真值：市场数据口径、策略配置、实验、baseline、live strategy registry、每日 live run、调仓包生成和研究审计。

PAMS owns 资产真值：账户、持仓、现金、资产负债、交易生命周期、通知、app/web 展示、用户审批和执行状态。

替代方案是继续让两个系统都能研究和管交易。该方案短期改动少，但会制造两个策略口径、两个审批来源和两个交易状态机，不建议推进。

### Decision 2: 用调仓包替代共享文件和重复计算

两个系统之间只传递 `daily_position_adjustment_package@1`。PAMS 不读取研究平台内部实验目录，不复算 action sheet，不根据 `portfolio_trades.csv` 或 `outputs/mobile_ops/*` 推导实盘建议。

调仓包最小结构：

- header：`schema_version`、`package_id`、`idempotency_key`、`generated_at`。
- source：`strategy_id`、`strategy_run_id`、`baseline_id`、`config_hash`、`execution_contract_hash`。
- clock：`signal_date`、`execution_date`、`signal_clock`、`execution_clock`、`reference_price_basis`。
- scope：`market`、`asset_scope`、`account_scope`、`currency`。
- inputs：`market_snapshot_id`、`holdings_snapshot_id`、`cash_snapshot_id`、`reconcile_id`。
- payload：`target_positions`、`action_sheet`、`risk_flags`、`validation`。

### Decision 3: 第一版交付以 PAMS 入站 API 为正式接口

长期正式接口为 PAMS 提供入站 API：

- `POST /api/live-signals/packages`
- `GET /api/live-signals/packages/{package_id}`
- `GET /api/live-signals/packages/latest?strategy_id=...&account_scope=...`

研究平台负责生成并提交调仓包。开发阶段可以保留 JSON 文件导出作为审计和调试镜像，但 PAMS 正式读写必须围绕数据库和 API，不依赖研究平台 `outputs/` 路径。

### Decision 4: live strategy 必须先注册再发布

研究平台必须有 live strategy registry。每个可发布策略至少记录：

- `strategy_id`
- `status`
- `baseline_id`
- `config_path`
- `config_hash`
- `execution_contract_hash`
- `asset_scope`
- `account_scopes`
- `publish_schedule`
- `approval_record`

只有 `status=live_approved` 的策略可以生成正式调仓包。`research_only`、`shadow`、`ab_test`、`retired` 均不得推送到 PAMS 主通知流。

### Decision 5: PAMS 只做账户约束和生命周期映射

PAMS 接收调仓包后可以做账户侧校验，例如现金、最小交易单位、账户权限、用户风险锁、重复动作、过期时间和当前持仓偏差。但这些校验只能生成 `blocked`、`adjusted`、`needs_review` 等账户侧状态，不能反向修改研究平台策略结论。

PAMS 将通过 `source_package_id`、`source_action_id`、`strategy_id`、`strategy_run_id`、`config_hash` 把交易生命周期记录与调仓包绑定。

### Decision 6: 旧逻辑冻结为 legacy，再迁移清理

PAMS 中旧 `strategy/*`、`backtest/*`、`backtest_v2*` 和复制版 `backtest_V2` 只能保留为 legacy 或迁移参考。后续新增研究能力必须进入量化研究平台。

研究平台现有 `mobile_ops`、`sim_account` 和 approval ticket 文件链路只作为过渡兼容，不作为长期跨系统产品边界。

## Risks / Trade-offs

- [Risk] 调仓包 schema 过早膨胀，导致第一版实现困难。→ Mitigation：第一版只要求最小 header/source/clock/scope/action_sheet/validation 字段，扩展字段必须向后兼容。
- [Risk] PAMS 旧策略扫描继续运行，造成双口径通知。→ Mitigation：实施阶段先增加 legacy 标记和调度禁用开关，再迁移或删除。
- [Risk] 研究平台和 PAMS 对账户 ID、证券代码、市场代码定义不一致。→ Mitigation：调仓包必须显式携带 `account_scope`、`market`、`asset_class`、`symbol_namespace`。
- [Risk] 重复推送导致重复通知或重复审批。→ Mitigation：`package_id` 和 action 级 `idempotency_key` 必须入库唯一约束。
- [Risk] 调仓包被误认为成交事实。→ Mitigation：调仓包只代表研究建议和账户侧草稿，成交事实只能来自 PAMS 交易生命周期回写。
- [Risk] 文件镜像被长期依赖。→ Mitigation：所有文件镜像必须标注 `compat_only` 或 `audit_copy`，正式接口以 PAMS API/DB 为准。

## Migration Plan

1. 建立本规格和验收清单，不改核心运行行为。
2. 在研究平台新增 live strategy registry 和调仓包生成器，只输出 package，不推送。
3. 在 PAMS 新增 package 入站表、action 表、幂等约束和只读查询接口。
4. 接通研究平台到 PAMS 的提交路径，并保留审计 JSON 镜像。
5. 将 PAMS app/web 通知从旧 `pams_order_drafts` 切到 package/action 视图。
6. 将 PAMS 旧策略扫描和旧回测入口标记 legacy，并从生产调度中移除。
7. 将研究平台移动端审批/执行链路降级为内部预览或兼容路径，长期审批状态以 PAMS 事务域为准。

Rollback 策略：

- 如果 PAMS 入站失败，研究平台仍可生成调仓包审计文件，但不得绕过 PAMS 直接推送用户。
- 如果 package schema 校验失败，PAMS 必须拒收并记录失败原因，旧资产管理功能不受影响。
- 如果通知切换失败，可临时关闭 package 通知，仅保留入库和查询。

## Open Questions

- 第一版 PAMS 是否只支持本机内网 API，还是需要公网/反向代理访问。
- `account_scope` 是否先用单账户字符串，还是从第一版就支持多账户组合。
- PAMS app/web 第一版展示是“调仓建议列表”还是直接进入“审批草稿”。
- 研究平台 live strategy registry 第一版落在配置文件、SQLite/Postgres，还是复用现有 baseline index。
