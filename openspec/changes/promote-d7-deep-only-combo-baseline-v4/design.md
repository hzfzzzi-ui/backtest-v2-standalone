## Decision

### 1. V4 绑定对象

V4 只绑定全周期 `1226` 的 unified combo 实验：

- baseline id: `CN_STOCK_ETF_COMBO_BASELINE_V4`
- linked exp: `exp_20260511_073506050_3d22`
- source study: `cn_stock_etf/cn_stock_etf_high_chase_d5_deep_mae_combo_ab_v1`
- variant: `HC_D5_DEEP_ONLY_IMMEDIATE_COMBO`
- effective start: `2012-07-12`

不使用 `1217` 或 `1626` 作为 baseline truth，因为它们都不是完整 live baseline 生效期。

### 2. 为什么新建 V4 而不是重挂 V3

这次是组合主线的代际升级，不是对 V3 做静默重写。与刚才 stock baseline 重挂不同，combo 侧已经有稳定引用 `CN_STOCK_ETF_COMBO_BASELINE_V3` 作为历史研究锚点，因此更合理的做法是：

1. 新建 `CN_STOCK_ETF_COMBO_BASELINE_V4`
2. 保留 `CN_STOCK_ETF_COMBO_BASELINE_V3`
3. 将 V3 标记为 `superseded`

这样历史研究仍然可以继续明确引用 V3，不会把旧研究对照 silently 改写成 V4。

### 3. 风险接受口径

这次 promotion 不是“组合 headline 指标已经显著胜出”的常规升级，属于用户明确批准的人工 override。

必须保留的事实：

- `HC_D5_DEEP_ONLY_IMMEDIATE_COMBO` 的 full-cycle combo headline 相对 V3 基本持平，甚至略弱：
  - CAGR `-0.0401pp`
  - Sharpe `-0.00088`
  - Calmar `-0.00098`
  - MaxDD `+0.0128pp`
- 它的正面证据主要来自：
  - 与新 stock baseline D7 deep-only 一致
  - stock 腿 drawdown repair 成立
  - main / hard-gate 窗口可接受

所以 V4 必须以“user-approved override baseline”写入 promotion note，而不能伪装成纯指标胜出。

### 4. 默认入口

V4 promotion 完成后，需要同步切换：

- 桌面端默认 bootstrap baseline id
- foundation baseline regression current anchor
- 对应的最小测试断言

历史研究 YAML、历史 study round 和只读审计脚本不强制迁移，除非它们本来就表示“当前 active baseline”。

### 5. 回退

回退路径：

1. 将 `CN_STOCK_ETF_COMBO_BASELINE_V4` 标记为 `superseded` 或移除 active 身份。
2. 将 `CN_STOCK_ETF_COMBO_BASELINE_V3` 恢复为 `active`。
3. 恢复桌面 bootstrap baseline 和 foundation regression contract 到 V3。
4. 刷新 `outputs/baselines/index.json`。
