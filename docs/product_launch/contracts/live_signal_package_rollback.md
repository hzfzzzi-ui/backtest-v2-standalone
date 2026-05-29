# Live signal package rollback

## 适用范围

本文用于 `backtest_V2_standalone` 与 PAMS 的 live 调仓包链路回退。回退不得修改 baseline、信号时点、执行时点、策略配置或研究口径。

## 关闭研究平台推送

1. 将 live package publisher 的运行模式切到 `audit_copy` 或停止提交到 PAMS API。
2. 保留生成的 `daily_position_adjustment_package@1` JSON 作为审计文件。
3. 不允许绕过 PAMS，直接把研究平台 action sheet 推送给 app/web 或用户。

## 关闭 PAMS package 通知

1. 停止调用 `POST /api/live-signals/packages/{package_id}/notifications`。
2. 已入库的 `pams_live_signal_packages`、`pams_live_signal_actions` 和 `pams_live_signal_transaction_lifecycle` 保留为审计记录。
3. PAMS app/web 回退到只读资产管理展示，不从 `pams_order_drafts` 恢复正式实盘建议。

## 临时恢复 legacy 调度

默认值必须保持：

```text
PAMS_LEGACY_STRATEGY_JOBS_ENABLED=false
```

如需短期审计或人工排障，可临时设置为 `true` 并重启 PAMS scheduler。恢复前必须确认 package 通知已经关闭，避免同一策略出现双通知。

## 恢复 package 链路

1. 确认研究平台 registry 中策略仍为 `live_approved`。
2. 确认 `baseline_id`、`config_hash` 和 `execution_contract_hash` 与 registry 一致。
3. 先提交 `dry_run` package 到 PAMS 测试入站链路。
4. 验证 package 查询、通知、审批、transaction lifecycle 均能追溯到 `package_id` 和 `action_id`。
5. 再恢复 `publish_mode=live`。
