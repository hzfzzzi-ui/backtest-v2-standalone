## 1. OpenSpec 与研究入口

- [x] 1.1 完成 `add-etf-research-mainline-r1` 的 proposal/design/specs 产物并通过 `openspec validate`。DoD: change 至少到 apply-ready；验证: `openspec validate add-etf-research-mainline-r1 --type change --strict`；风险: 误把 research-only 语义写进 formal ETF sleeve。
- [x] 1.2 新增 `research/studies/etf/cn_broad_based_research_mainline_r1.study.yaml` 与 generated thin script。DoD: study 可被 `study_loader` 装载，脚本可指向 `study_run etf/cn_broad_based_research_mainline_r1`；验证: dry-run 或 `study_runner.build_execution_plan`；风险: study id、脚本名或路径不一致。

## 2. 最小回归保护

- [x] 2.1 新增最小 unit test，锁定 R1 study 的关键执行计划字段。DoD: 至少覆盖 biweekly、core_growth_slot、唯一 growth seat、双防守和 `RISK_OFF` 单 seat 语义；验证: `pytest` 通过；风险: 只测装载不测关键策略字段，导致后续静默漂移。

## 3. 回测与产物校验

- [x] 3.1 运行 R1 主线的 `2012-2026` 回测。DoD: 生成实验目录与标准产物；验证: `perf.json`、`run_meta.json`、`audit.json` 可读；风险: 数据覆盖或 study 运行入口失败。
- [x] 3.2 记录核心结果与回退路径。DoD: 明确说明收益、回撤、交易数、弱市承接是否生效；验证: 结果总结引用实际产物；风险: 只给收益，不说明风险和解释性证据。
