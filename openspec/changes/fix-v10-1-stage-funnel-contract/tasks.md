## 1. 基线锚点

- [x] 1.1 固定一组 V10.1 漏斗回归锚点；DoD: 选定一个稳定实验作为前后对比样本并记录 `portfolio_daily.csv`、`run_meta.json`、结果工作台漏斗现状；验证: 能对同一实验重复比对 daily_row、`buy_stage_funnel` 和前端视图；风险: 选到不稳定样本会放大无关噪声
- [x] 1.2 明确 counted / derived / unavailable 的验收样例；DoD: 为至少一个真实零值阶段和一个 unavailable 阶段准备可验证样本；验证: 后续实现后可直接判断“真实 0”与“未单独计数”是否被区分；风险: 样例覆盖不足会导致 UI 与 runtime 口径脱节

## 2. 前端语义纠偏

- [x] 2.1 收紧结果工作台漏斗 helper 的空值语义；DoD: `stageFunnelFormatting` 不再把 `available=false` 或 `null` 计数数值化为 `0`；验证: 相同实验在漏斗面板中显示 unavailable 状态而不是 0；风险: 旧实验目录可能缺少字段，需兼容历史产物
- [x] 2.2 对齐 workbench 与旧桥接层的漏斗展示语义；DoD: `frontend/app/results-workbench` 与 `frontend/assets/js/artifacts.js` 对 unavailable/zero 的判断一致；验证: 通过同一实验对比两个消费入口的 stage 状态；风险: 双 helper 并存时容易出现再次漂移

## 3. Runtime 诊断收口

- [x] 3.1 收紧 `daily_accounting` 的漏斗字段写入优先级；DoD: 买入漏斗字段优先读取 provider diagnostics 与 `debug_plan`，缺失时保留空值而不是回退到后置阶段数量；验证: `portfolio_daily.csv` 中前序阶段不再被 `len(day_signals.buy_signals)` 压平；风险: 改动过深会误触交易主链
- [x] 3.2 为可提供真实阶段计数的 provider 补齐稳定 diagnostics；DoD: `generic`、`regime_router`、`multi_alpha`、`breakout` 等路径对已知阶段输出稳定键名，对未知阶段不造数；验证: provider 产出的 `diagnostics` 能支持 daily_row 写入真实或空值语义；风险: 不同 provider 的候选定义可能不完全同义
- [x] 3.3 正式接入订单规划阶段计数；DoD: `after_slot_filter_count`、`after_cash_lot_count`、`selected_count` 由 planner/debug_plan 明确供给，不再通过最终订单数反推；验证: 同一交易日的 planner 输出与 daily_row 对齐；风险: planner 字段命名不统一会导致接线错误

## 4. Artifact 聚合一致性

- [x] 4.1 收紧 `artifacts_impl` 的 `stage_funnel` 聚合语义；DoD: lazy section 与 `run_meta.counters.buy_stage_funnel` 同时保留 `available` 和 `null` 语义；验证: 两个输出面对同一阶段给出一致的 unavailable/zero 结论；风险: 旧实验兼容层可能继续偷偷补数
- [x] 4.2 补充 counted / unavailable 的聚合回归检查；DoD: 至少覆盖“真实为 0”和“当前未单独计数”两种阶段；验证: 聚合层不会把空值写成 0，也不会把真实 0 误判成 missing；风险: 只验证 happy path 会遗漏边界样本

## 5. 回归验证与回退

- [x] 5.1 运行漏斗合同回归并确认交易结果不漂移；DoD: 同一基线实验的收益、回撤、交易笔数、NAV 与修复前一致，仅漏斗诊断和展示变化；验证: 对比 `perf.json`、`nav.csv`、交易统计和漏斗输出；风险: 若只看 UI 而不看回测结果，容易放过越界改动
- [x] 5.2 记录实现后的验证命令、观察点与回退条件；DoD: 在 change 或实现说明中明确如何复跑、看哪些产物、何种漂移必须整轮回退；验证: 他人可按文档重复检查这次修复；风险: 若回退条件不清晰，后续容易把诊断修复误当成策略优化
