# Tasks: regime-signal-decomposition

## Phase 1: 后端拆分

- [x] 1.1 新建 `backend/core/strategies/rsi_reversal.py` — 从 `adaptive_regime._generate_mr_signals()` 提取 RSIReversalStrategy 类，实现 `generate_signals()` 接口
- [x] 1.2 新建 `backend/core/strategies/regime_router.py` — RegimeDetector（从 `adaptive_regime._detect_regime` 提取）+ RegimeRouter 路由壳
- [x] 1.3 RegimeRouter 实现 MR 遗留持仓跟踪（`state["mr_symbols"]`）和 `_generate_mr_exit_only` 委托逻辑
- [x] 1.4 `registry.py` 新增 `rsi_reversal` 分支和 `regime_router` 分支
- [x] 1.5 `registry.py` 的 `adaptive_regime` 分支改为构造 RegimeRouter(SMA + RSI)（向后兼容）
- [x] 1.6 `portfolio_simulator_strict.py` 的 isinstance 检查加入 RegimeRouter

## Phase 2: 前端面板重构

- [x] 2.1 `index.html` Signal Generation 区域重构: 去掉 wbStrategyFamily 顶层选择器，改为三个 `<details>` 子面板（市况判断 + 趋势模式 + 震荡模式）
- [x] 2.2 市况判断面板: 启用 checkbox + regime_ma 输入框
- [x] 2.3 趋势模式面板: 策略选择器 (SMA/EMA) + 复用现有参数面板
- [x] 2.4 震荡模式面板: 策略选择器 (RSI_REVERSAL) + RSI 参数 + hold/stop 参数（仅 regime 启用时显示）
- [x] 2.5 `ui-controls.js` — `buildConfigDraft()` 按新 JSON 结构序列化（regime_detection + trend + mr 三层）
- [x] 2.6 `ui-controls.js` — `applyConfigToUI()` 反序列化新结构 + 兼容旧 adaptive_regime 格式
- [x] 2.7 `ui-controls.js` — `renderSummaryBar()` 按新格式显示摘要

## Phase 3: API 编译路径

- [x] 3.1 `_experiment_runner_api.py` — 新增 regime_router 编译路径（解析 regime_detection + trend + mr）
- [x] 3.2 `_experiment_runner_api.py` — 保留旧 adaptive_regime 编译路径做格式转换（向后兼容）

## Phase 4: Docker 构建与验证

- [x] 4.1 Docker rebuild + 启动
- [x] 4.2 冒烟测试: regime 启用 + SMA + RSI 组合，验证与旧 adaptive_regime 行为一致
- [x] 4.3 组合测试: regime 启用 + EMA + RSI 组合，验证 EMA 信号在 TREND 模式正确生成
- [x] 4.4 退化测试: regime 关闭时退化为纯 SMA，验证与 SMA_CROSS 策略行为一致
