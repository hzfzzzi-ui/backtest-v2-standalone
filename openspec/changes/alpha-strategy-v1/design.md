## Context

当前回测系统已实现完整的向量化引擎（portfolio_simulator_strict.py）、三个 SignalProvider（SMA/Generic/RegimeRouter）、动量排序（strength_rank）和多因子排序（multifactor_rank）。但 HTTP API 层未透传 strength_rank 相关参数，导致所有通过 API 发起的实验均未启用动量选股。

基线 EMA(8,25) 在 2015-2025 全 A 800 只、30bp 成本下 CAGR=-4.74%。距目标 CAGR>=10% 差 ~15pp。

研究计划已完成：
- `docs/research/alpha_strategy_v1/strategy_specs.md` — 三策略详细设计
- `docs/research/alpha_strategy_v1/experiments_plan.md` — 55 次实验矩阵

## Goals / Non-Goals

**Goals:**
- 修复 API 层 strength_rank 参数断裂（P0，必须先于实验）
- 编写自动化实验脚本 `run_alpha_v1.py` 驱动 55 次 API 回测
- 实现决策门（Gate）自动判断 Go/No-Go
- 后处理：walk-forward 汇总、牛熊分段、成本敏感度、参数稳定性
- 生成可复现的研究报告 `final_report.md`

**Non-Goals:**
- 不修改引擎核心逻辑（所有策略参数已在 `run_portfolio_backtest()` 签名中支持）
- 不添加新策略类型（使用现有 EMA_CROSS + REGIME_ROUTER）
- 不修改前端 UI（纯后端 + 脚本变更）
- 不做实时交易对接

## Decisions

### D1: 实验脚本架构——单文件 HTTP 客户端

**选择**: 单文件 `backend/scripts/run_alpha_v1.py`，通过 HTTP API 提交实验

**替代方案**: (A) 直接调用 `run_experiment()` Python 函数 (B) 扩展现有 batch_runner.py

**理由**:
- HTTP API 路径与生产环境一致，实验结果可直接复现
- 单文件便于在 Docker 容器内/外运行
- batch_runner.py 是通用工具，不适合承载策略研究逻辑

### D2: 实验分阶段 + 决策门

**选择**: Phase 0 → Gate 0 → Phase 1 → Gate 1 → Phase 2/3 → Final Report

**理由**:
- Gate 0（strength_rank 改善 >= 3pp）验证核心假设
- Gate 1-3（CAGR > 0%）避免浪费计算资源在失败策略上
- 允许手动干预：脚本在每个 gate 暂停等待确认

### D3: Walk-Forward 窗口切片

**选择**: 10 × 1 年窗口（2015-2016, 2016-2017, ..., 2024-2025）

**替代方案**: 滚动窗口、扩展窗口

**理由**: 固定 1 年窗口最简单、与年度业绩报告对齐、10 个样本足够评估稳定性

### D4: 牛熊分段定义

**选择**: 基于 CSI800 + EMA(200) + 200 日收益率

**理由**: 与 strategy_specs.md 中定义一致，使用长周期 EMA 避免频繁切换

### D5: API 修复范围——最小侵入

**选择**: 仅在 `BacktestV2ExperimentRequest` 添加 5 个 Optional 字段 + overrides builder 透传

**理由**: 引擎和 experiment_runner.py 已支持这些参数，只是 API 层缺失

## Risks / Trade-offs

- **[风险] 55 次回测计算量大（~4-7 小时）** → 缓解：Phase 分段执行，失败提前终止
- **[风险] OHLCV-only alpha 目标过于激进** → 缓解：设置 soft target (8%) 和 hard target (10%)，记录失败原因
- **[风险] API 修复后需 Docker rebuild** → 缓解：修复代码量极小（~10 行），rebuild 风险低
- **[权衡] 单文件脚本 vs 模块化** → 选择简单性：研究脚本是一次性工具，不需要长期维护
- **[权衡] HTTP API vs 直接函数调用** → 选择一致性：API 路径确保实验与生产行为一致
