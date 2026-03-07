## 1. P0: API 层 strength_rank 参数透传

- [x] 1.1 在 `_experiment_runner_api.py` 的 `BacktestV2ExperimentRequest` 添加 5 个 Optional 字段：`enable_strength_rank`, `strength_ma`, `strength_top_k_mode`, `enable_multifactor_rank`, `mf_topk`
- [x] 1.2 在 `_build_runtime_cfg_from_workbench()` 或 overrides builder 中透传这 5 个字段到 `run_experiment()` overrides 字典

## 2. 实验脚本核心框架

- [x] 2.1 创建 `backend/scripts/run_alpha_v1.py` 基础框架：HTTP 客户端（submit_job / poll_job / extract_metrics）、CLI 入口、logging
- [x] 2.2 实现实验参数构建器：从 experiments_plan.md 的参数矩阵生成每组实验的完整 overrides 字典（B0/B1、S1 × 5、S2 × 5、S3 × 4）
- [x] 2.3 实现 Phase 调度逻辑：Phase 0 → Gate 0 → Phase 1A → Gate 1 → Phase 1B/1C → Phase 2/3

## 3. Walk-Forward 与成本敏感度

- [x] 3.1 实现 WF 窗口切片：将 10 年区间切为 10 × 1 年窗口，对最佳变体逐窗口提交回测
- [x] 3.2 实现成本敏感度矩阵：对最佳变体提交 5bp/15bp/50bp 额外回测（30bp 复用 Phase A 结果）

## 4. 后处理与报告

- [x] 4.1 实现 wf_summary 后处理：从 10 次 WF 结果计算每年 CAGR/Sharpe/MaxDD，输出 CSV + 中位数/正收益年数
- [x] 4.2 实现牛熊分段分析：基于 CSI800 EMA(200) 将日收益分配到 Bull/Bear/Sideways 段，输出分段 CAGR
- [x] 4.3 实现参数稳定性检查：比较邻近参数变体的 Sharpe 差异是否在 ±0.15 以内
- [x] 4.4 实现 final_report.md 生成：三策略横向对比表、最佳推荐、Pass/Fail 检查清单、风险评估
