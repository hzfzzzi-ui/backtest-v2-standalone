## ADDED Requirements

### Requirement: MA200 状态机必须降级为显式 fallback 模式
`ma200-market-state` SHALL 不再被视为正式市场状态真相源，而 MUST 作为 `market-regime-framework` 未启用、特征不可用或用户显式指定时的兼容 fallback 模式。系统 MUST 在运行元数据中明确标识当前使用的是 `ma200_legacy`，避免与正式 regime framework 混淆。

#### Scenario: 用户显式选择 legacy 模式
- **WHEN** 用户在配置中指定 `regime_engine = ma200_legacy`
- **THEN** 系统 MUST 使用现有 MA200 四态逻辑，并在产物中标记 `regime_engine = ma200_legacy`

#### Scenario: 正式框架特征不可用时回退
- **WHEN** 正式市场状态框架因特征覆盖不足而无法运行，且配置允许回退
- **THEN** 系统 MUST 明确回退到 `ma200_legacy`，并记录回退原因

### Requirement: MA200 fallback 输出必须带兼容语义标记
在 `ma200_legacy` 模式下，系统 SHALL 继续输出现有 `BULL / TRANS_UP / TRANS_DOWN / BEAR` 和 `TREND_MAIN / TREND_LIGHT / NO_TRADE`，但 MUST 同时输出：
- `regime_engine`
- `regime_semantics = legacy_price_filter`

#### Scenario: 前端展示区分 legacy 与正式框架
- **WHEN** 前端加载一条使用 MA200 fallback 的实验
- **THEN** 结果页 MUST 能识别该状态线属于 legacy 价格过滤器，而不是正式多因子 regime 框架
