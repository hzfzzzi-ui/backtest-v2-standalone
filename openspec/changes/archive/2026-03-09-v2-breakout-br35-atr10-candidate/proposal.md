# Why

当前正式 candidate `v2-breakout-atr-stop-k10-candidate` 已将 `atr_stop_k=1.0` 固化为显式候选入口，但最近一轮正式稳健性审查表明：在该底座上将 `breakout_window` 从 `55` 收紧到 `35`，比 `40` 更值得作为下一版主候选。

本次变更需要把“`ATR1.0` 底座 + `breakout_window=35`”收敛成新的 formal candidate，并同时补一个前端可直接加载的受控配置，便于人工检查结果而不依赖草稿手工回填。

# What Changes

- 新增 `v2-breakout-br35-atr10-candidate` locked candidate，以上一版 `ATR1.0` formal candidate 产物为锁定底座，只允许 `strategy.params.breakout_window=35` 单路径漂移。
- 保留旧的 `v2-breakout-atr-stop-k10-candidate`，不覆盖其 identity、证据链或回滚语义。
- 在前端运行 preset 中显式暴露新的 BR35 candidate。
- 在配置加载链路中新增一个内建配置：`BR35+ATR1.0+CSI800+10Y`，供前端“加载”菜单直接调用。
- 对新 candidate 做 API / artifact / frontend loading 的端到端验证，并在完成后重启容器。

# Impact

- OpenSpec: 新增一个独立 change，定义 BR35 candidate 的约束、证据包和回滚边界。
- Backend API: 扩展 locked candidate preset 分发与产物写出。
- Frontend: 增加一个新 preset 选项；加载配置链路通过 builtin config 自动暴露，不改变默认草稿运行行为。
- 研究纪律: 不修改成本、股票池、成交规则、评价口径；若使用 `t` 日收盘信号，继续 `t+1` 执行。
