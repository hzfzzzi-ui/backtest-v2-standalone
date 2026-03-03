## ADDED Requirements

### Requirement: 实验脚本自动提交多阶段回测
系统 SHALL 提供 `run_alpha_v1.py` 脚本，通过 HTTP API 自动提交 Phase 0-3 全部实验，每次实验携带完整的策略参数、退出规则、成本配置。

#### Scenario: Phase 0 基线提交
- **WHEN** 脚本执行 Phase 0
- **THEN** 系统提交 B0（无 strength_rank）和 B1（有 strength_rank）两次回测，返回 CAGR、Sharpe、MaxDD 等指标

#### Scenario: Phase 1 参数矩阵提交
- **WHEN** 脚本执行 Phase 1A
- **THEN** 系统提交 5 组 S1_MOMO 参数变体（CENTER/FAST/SLOW/TIGHT/LONG），每组使用不同的 fast_ma/slow_ma/trail_k/time_exit

### Requirement: 决策门自动判断
系统 SHALL 在每个 Phase 结束后执行决策门检查，根据预定义阈值判断 Go/No-Go。

#### Scenario: Gate 0 strength_rank 效果检查
- **WHEN** Phase 0 完成且 B1.CAGR - B0.CAGR < 3pp
- **THEN** 脚本输出警告并暂停，要求用户确认是否继续

#### Scenario: Gate 1 策略可行性检查
- **WHEN** Phase 1A 最佳变体 CAGR <= 0%
- **THEN** 脚本标记 S1_MOMO 为 FAIL，跳过 Phase 1B/1C

### Requirement: Walk-Forward 窗口切片
系统 SHALL 支持将 10 年区间切为 10 × 1 年窗口，对最佳参数变体逐窗口回测。

#### Scenario: 10 年 walk-forward 切片
- **WHEN** 脚本执行 Phase 1B 且最佳变体为 S1_CENTER
- **THEN** 系统提交 10 次回测（2015-2016, 2016-2017, ..., 2024-2025），每次使用 S1_CENTER 参数

### Requirement: 成本敏感度测试
系统 SHALL 对最佳参数变体进行 4 档成本测试（5bp/15bp/30bp/50bp）。

#### Scenario: 成本敏感度矩阵
- **WHEN** 脚本执行 Phase 1C
- **THEN** 系统提交 3 次额外回测（5bp/15bp/50bp，30bp 复用 1A 结果），输出成本-收益曲线数据

### Requirement: 后处理报告生成
系统 SHALL 从原始产物自动计算后处理分析表，并生成最终报告。

#### Scenario: Walk-forward 汇总表
- **WHEN** 10 次 WF 回测全部完成
- **THEN** 系统生成 wf_summary.csv 包含每年 CAGR/Sharpe/MaxDD，以及中位数和正收益年数

#### Scenario: 最终报告
- **WHEN** 所有 Phase 完成
- **THEN** 系统生成 final_report.md 包含三策略横向对比表、最佳推荐、风险评估
