## Why

当前 EMA(8,25) 基线在 30bp 成本下 10 年 CAGR=-4.74%，距离目标 CAGR>=10% 差 ~15pp。差距来源：(1) 震荡市大量虚假 MA 交叉信号，(2) 无选股质量——随机买入触发交叉的股票，(3) 高换手拖累（~200+次/年 × 70bp ≈ 12-15% 年化）。

本变更实施三套策略设计 + 55 次系统性实验，通过动量选股、制度自适应、低换手三个维度攻关 alpha，同时修复 API 层缺失的 `enable_strength_rank` / `enable_multifactor_rank` 透传（所有历史实验均未使用动量排序）。

## What Changes

- **P0 API 修复**：在 `BacktestV2ExperimentRequest` 中新增 `enable_strength_rank`、`strength_ma`、`strength_top_k_mode`、`enable_multifactor_rank`、`mf_topk` 字段，并透传到 overrides builder
- **实验脚本**：新建 `backend/scripts/run_alpha_v1.py`，通过 HTTP API 自动提交 ~55 次回测，实现 Phase 0-3 全流程（基线 → S1_MOMO → S2_REGIME → S3_LOWTURN）+ 决策门
- **后处理分析**：从原始产物计算 walk-forward 年度指标、牛熊分段、成本敏感度、参数稳定性、exit reason 分布
- **最终报告**：生成 `final_report.md` 包含三策略横向对比、最佳变体推荐、风险评估

## Capabilities

### New Capabilities
- `alpha-experiment-runner`: 自动化多策略实验总线——提交、轮询、收集、后处理、决策门判断
- `strength-rank-api-passthrough`: HTTP API 透传动量排序参数（enable_strength_rank, strength_ma, enable_multifactor_rank 等）

### Modified Capabilities
- `batch-experiment-runner`: 扩展实验运行器支持 walk-forward 窗口切片和成本敏感度矩阵
- `single-run-pipeline`: exit_rules / position_risk / costs 配置需完整透传到引擎（当前 strength_rank 断裂）

## Impact

- **后端 API**: `_experiment_runner_api.py` 新增 5 个请求字段 + overrides builder 透传（~10 行）
- **脚本**: 新建 `backend/scripts/run_alpha_v1.py`（~300-400 行）
- **文档**: 新建 `docs/research/alpha_strategy_v1/final_report.md`（实验完成后生成）
- **现有引擎**: 无改动——所有参数已在 `run_portfolio_backtest()` 签名中支持
- **Docker**: API 修复后需 rebuild 镜像
