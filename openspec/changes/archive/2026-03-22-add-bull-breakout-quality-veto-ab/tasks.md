# Tasks

## 1. Spec

- [x] 1.1 补充 `bull-breakout-quality-veto` capability spec，明确 veto 作用域、阈值和最小 A/B 合同
- [x] 1.2 补充 `signal-provider-protocol` delta spec，声明 bull breakout veto 的稳定 diagnostics / counters 输出

## 2. Implementation

- [x] 2.1 在配置模型、semantic schema 和 runtime compiler 中增加 bull breakout quality veto 的可选字段
- [x] 2.2 在 `BreakoutProviderConfig` 与 provider config builder 中透传 veto 参数
- [x] 2.3 在 breakout provider 的买入候选循环中接入 `BULL + breakout/overlap` 单侧 veto
- [x] 2.4 在 provider / result bridge / run_meta 中补稳定计数器与诊断输出，保证 `run_meta.json` 可审计

## 3. Verification

- [x] 3.1 补单测，覆盖：
  - veto 默认关闭时行为不变
  - `BULL` 内低 residual / 低 breakout margin 候选会被阻断
  - 非 `BULL` 或非 breakout 候选不受影响
- [x] 3.2 运行定向单测与语法检查

## 4. AB

- [x] 4.1 新增最小 AB 脚本，复用当前正式 `baseline_V10.2`，只切入 bull breakout veto
- [x] 4.2 运行 A/B，生成 `summary / report / performance_comparison / bull_trade_quality_comparison`
- [x] 4.3 明确 intended diff、风险、验证与回退路径
