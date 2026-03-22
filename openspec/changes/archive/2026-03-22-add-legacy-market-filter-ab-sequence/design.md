# Design

## Context

当前主线 `baseline_V10.2` 使用 `ma200_legacy` 作为市场过滤器。已有分析已经证明：

- 直接用 `weekly_five_state` 替换主线不成立
- `TURN_WEAK -> 0` 这类 veto 规则迁移到 legacy 也不成立
- `legacy` 的问题更像是过渡阶段执行过宽，而不是整套大方向状态定义都错

因此这次设计目标不是替换状态机，而是在 legacy 上做最小、按顺序推进的执行层 A/B，验证问题究竟在：

- `TRANS_UP / TRANS_DOWN` 预算映射
- `TRANS_UP` 新开仓权限
- 长均线窗口反应速度

## Goals / Non-Goals

**Goals:**

- 为 `ma200_legacy` 增加最小可配置实验面，支持 AB1 / AB2 / AB3 顺序实验
- 保持 intended diff 清晰，单轮只新增一个主变量
- 让配置透传到运行时与研究脚本，保证前后端和实验产物一致
- 输出正式对照产物，能够直接比较 legacy / AB1 / AB2 / AB3

**Non-Goals:**

- 不替换 `ma200_legacy` 为新的状态机
- 不修改个股信号、股票池、退出逻辑
- 不引入宏观变量、量能新特征或新的 market regime engine
- 不在本 change 内解决 `TRANS_UP` 所有问题，只验证最小假设

## Decisions

### 决策 1：AB1 只拆 `TRANS_UP / TRANS_DOWN` multiplier

原因：

- 当前 legacy 已经支持状态相关 multiplier，改动成本最低
- 可以直接验证“问题是不是 `TRANS_UP` 预算过宽”
- 不需要改变状态机定义或开仓条件

备选方案：

- 直接改 `MA200 -> MA120`
  - 否决原因：影响范围过大，归因会变脏

### 决策 2：AB2 用买入后处理层实现 `TRANS_UP` 禁新开仓

原因：

- 只需要在 `postprocess_day_signals` 层基于 legacy `market_state` 清空买入信号
- 不改原始 `market_state / trade_mode` 语义
- 已有持仓仍可沿用现有退出链，风险最小

备选方案：

- 把 `TRANS_UP` 直接改成 `NO_TRADE`
  - 否决原因：会同时改 `trade_mode` 语义和计数器，难以与 AB1/AB3 归因分开

### 决策 3：AB3 只把 `long_ma_window 200 -> 160`

原因：

- 这是对大方向判定最小的一步提速
- 比直接跳到 `120` 更稳健
- 可以验证“问题是否来自长均线过慢”

备选方案：

- 直接 `200 -> 120`
  - 否决原因：改动太大，且与用户要求的最小 AB 顺序不一致

### 决策 4：新增独立 A/B 脚本，不污染正式 baseline

原因：

- 研究实验应继续走最小脚本产物路径
- baseline 正式锚点不应被序列 AB 污染
- 便于直接输出 `summary / report / performance_comparison`

## Risks / Trade-offs

- [风险] `TRANS_UP` 禁新开仓可能和已有 `TREND_LIGHT` 预算叠加，造成交易过少  
  → 通过 AB1 与 AB2 顺序比较，单独确认冻结新买的边际影响

- [风险] `long_ma_window` 参数化会影响多个 legacy 代码路径  
  → 统一只改 legacy 公共计算点，并补单测与时点审计测试

- [风险] AB1/AB2/AB3 共用同一脚本时容易引入多重 intended diff  
  → 每组都从同一 `baseline_V10.2` 源配置克隆，并明确记录单组 diff

- [风险] legacy 实验和宿主机 PIT 连接可能不稳定  
  → 最终结果以容器内正式运行产物为准

## Migration Plan

1. 补齐 change 的 delta spec 和任务
2. 为 `MarketFilterConfig` 增加实验字段，并完成 schema/compiler 透传
3. 在 legacy 路径中接入：
   - `trans_down_multiplier`
   - `trans_up_multiplier`
   - `freeze_trans_up_entries`
   - `long_ma_window`
4. 补单测，确保 legacy 默认行为不变
5. 编写并运行 AB1 / AB2 / AB3 研究脚本
6. 生成正式对照报告

回退策略：

- 删除新增配置字段与接线
- 删除 A/B 脚本与产物
- 保持 `ma200_legacy` 默认配置不变即可恢复原行为

## Open Questions

- AB2 若有效，后续是只保留“冻结新买”，还是继续研究“加速 carry 仓去风险”，本 change 不解决
- AB3 若改善不足，后续是否继续测试 `160 -> 120`，本 change 不预先承诺
