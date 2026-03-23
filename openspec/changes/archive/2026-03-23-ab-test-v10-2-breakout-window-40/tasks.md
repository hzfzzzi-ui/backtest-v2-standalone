## 1. 研究定义

- [x] 1.1 编写 proposal、design 和 delta spec，限定本次为 `baseline_V10_2` 上的单变量 `breakout_window` A/B；DoD：变更意图、边界和输出口径写清；验证：`openspec status --change ... --json` 可见 artifacts 齐备；风险：把参数实验写成正式 baseline 变更。
- [x] 1.2 新增 `research/studies/v10/breakout_window_40_ab.study.yaml` 并生成 thin script；DoD：study 可被 loader 识别且包含 `B0/BW40` 两个变体；验证：`python -m backend.cli study_run ... --dry-run`；风险：patch 路径写错导致不是单变量实验。

## 2. 契约校验

- [x] 2.1 增加最小研究契约测试，锁定 `BW40` 只改 `signal_generation.breakout.breakout_window`；DoD：测试能覆盖 study 定义和 generated script；验证：`pytest tests/unit/test_v10_study_migration_contracts.py tests/unit/test_script_surface_governance.py -q`；风险：只测脚本存在，不测 payload 差异。

## 3. 实验执行与结论

- [x] 3.1 运行 study dry-run，确认执行 payload 继承 `baseline_V10_2` 且只改 breakout window；DoD：dry-run 输出可读且差异清晰；验证：CLI dry-run 结果；风险：隐性配置漂移未被发现。
- [x] 3.2 执行 A/B study，生成 `B0=45` 与 `BW40=40` 两个实验结果及 compare 产物；DoD：两个 `exp_id` 和 compare bundle 都落盘；验证：`python -m backend.cli study_run ... --skip-baseline-append`；风险：把探索性结果写进 baseline 台账。
- [x] 3.3 汇总绩效、回撤、交易行为和结论，判断 `40` 是否值得进入下一轮研究；DoD：输出中明确事实、风险、验证和回退；验证：对比 `perf.json/run_meta.json` 与 study 输出；风险：只看收益不看行为漂移。
