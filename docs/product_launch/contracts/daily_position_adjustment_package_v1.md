# daily_position_adjustment_package@1 合同

## 定位

`daily_position_adjustment_package@1` 是量化研究平台向 PAMS 发布 live 策略每日仓位调整建议的唯一正式合同。它不是成交事实，不是账户真值，也不允许 PAMS 反向复算研究策略。

## 版本

- `schema_version`: `daily_position_adjustment_package@1`
- 兼容策略：新增字段必须向后兼容；删除字段或改变字段语义必须升级 schema version。
- 正式接口：研究平台生成 package；PAMS 校验、幂等入库、通知、审批和交易生命周期映射。

## 必填结构

| 字段 | 说明 |
|---|---|
| `header.schema_version` | 固定为 `daily_position_adjustment_package@1` |
| `header.package_id` | package 唯一标识 |
| `header.idempotency_key` | package 幂等键，PAMS 必须唯一约束 |
| `header.generated_at` | 生成时间 |
| `source.strategy_id` | live 策略 ID |
| `source.strategy_run_id` | 本次 live run ID |
| `source.baseline_id` | 关联 baseline |
| `source.config_hash` | 配置哈希 |
| `source.execution_contract_hash` | 执行合同哈希 |
| `source.publish_mode` | `live` / `dry_run` / `audit_copy` |
| `clock.signal_date` | 信号日期 |
| `clock.execution_date` | 建议执行日期 |
| `clock.signal_clock` | 信号时钟说明 |
| `clock.execution_clock` | 执行时钟说明 |
| `clock.reference_price_basis` | 参考价格口径 |
| `scope.market` | 市场，例如 `CN_A` |
| `scope.asset_scope` | 资产范围，例如 `cn_a_equity` |
| `scope.asset_class` | 资产类别，例如 `equity` |
| `scope.account_scope` | PAMS 账户范围 |
| `scope.currency` | 计价货币 |
| `scope.symbol_namespace` | 证券代码命名空间 |
| `inputs.market_snapshot_id` | 市场数据快照 |
| `inputs.holdings_snapshot_id` | 持仓快照 |
| `inputs.cash_snapshot_id` | 现金快照 |
| `inputs.reconcile_id` | 持仓感知 reconcile 标识 |
| `package_status` | `ready` / `no_op` / `blocked` / `invalid` |
| `target_positions` | 目标仓位列表 |
| `action_sheet` | 调仓动作列表 |
| `risk_flags` | 风险标记 |
| `validation` | 发布前校验结果 |

## action_sheet 必填字段

每条 `action_sheet` 记录必须足够让 PAMS 做账户侧校验、展示、通知和审批草稿，但不能要求 PAMS 反向复算研究策略。

| 字段 | 说明 |
|---|---|
| `action_id` | action 唯一标识 |
| `idempotency_key` | action 幂等键，PAMS 必须唯一约束 |
| `symbol` | 标的代码 |
| `market` | 市场，例如 `CN_A` |
| `asset_class` | 资产类别，例如 `equity` |
| `action_type` | `buy` / `sell` / `increase` / `reduce` / `rebalance` / `hold` |
| `action_status` | `proposed` / `blocked` / `no_op` |
| `current_qty` | 研究平台生成建议时看到的持仓数量快照 |
| `target_qty` | 目标数量 |
| `delta_qty` | 目标数量与当前数量的差值 |
| `suggested_qty` | 建议操作数量 |
| `target_weight` | 目标权重 |
| `reference_price` | 参考价格，不是成交价 |
| `reference_price_basis` | 参考价格口径 |
| `estimated_amount` | 估算金额，可为空 |
| `reason_code` | 主原因代码 |
| `reason_tags` | 辅助原因标签 |
| `reason_codes` | PAMS 可直接消费的原因代码集合 |
| `blocked` | action 是否已在研究平台侧被阻断 |
| `blocked_reason` | 阻断原因，可为空字符串 |
| `expires_at` | 建议过期时间 |

## 状态规则

- `ready`: 必须至少包含一条 `action_sheet`。
- `no_op`: 可以没有调仓动作，但必须显式发布 no-op 状态，不能静默跳过。
- `blocked`: 必须给出 `validation.failure_reason_codes`。
- `invalid`: 必须给出 `validation.failure_reason_codes`，PAMS 必须拒收或入失败审计表。
- `validation.status=passed` 时不得携带失败原因。

## PAMS 侧禁止事项

- 不得读取研究平台 `outputs/` 目录推导实盘建议。
- 不得根据 `portfolio_trades.csv`、`mobile_ops` 或文件型 approval ticket 复算 package。
- 不得把 package 当作成交事实；成交事实只能来自 PAMS 交易生命周期回写。
- 不得反向修改研究平台策略结论；账户侧只能生成 blocked、adjusted、needs_review 等 PAMS 状态。

## Python 校验入口

研究平台内的最小校验入口：

```python
from backend.core.contracts import validate_daily_position_adjustment_package

package = validate_daily_position_adjustment_package(payload)
```

该入口用于单测、fixture 校验和后续 live package publisher 发布前门禁。
