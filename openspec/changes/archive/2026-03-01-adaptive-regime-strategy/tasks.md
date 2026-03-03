# Tasks: adaptive-regime-strategy

## Phase 1: 后端核心实现

- [x] 1.1 在 features.py 的 FeatureMatrices 新增 rsi 字段，compute_feature_matrices 新增 rsi_period 参数和 RSI 列式计算逻辑
- [x] 1.2 新建 backend/core/strategies/adaptive_regime.py — AdaptiveRegimeStrategy 类，实现 generate_signals 接口
- [x] 1.3 在 adaptive_regime.py 内实现 regime 检测逻辑（benchmark close vs benchmark MA）
- [x] 1.4 在 adaptive_regime.py 内实现趋势模式信号逻辑（SMA cross up/down）
- [x] 1.5 在 adaptive_regime.py 内实现均值回归模式信号逻辑（RSI oversold buy / overbought sell / time exit / stop loss）
- [x] 1.6 在 registry.py 注册 adaptive_regime 策略
- [x] 1.7 在 portfolio_simulator_strict.py 入口处识别 AdaptiveRegimeStrategy 并路由到 generic_signals 路径

## Phase 2: API + 前端集成

- [x] 2.1 在 _experiment_runner_api.py 的 _build_runtime_cfg_from_workbench 新增 ADAPTIVE_REGIME 策略包编译路径
- [x] 2.2 在前端 ui-controls.js 策略选择器中新增 ADAPTIVE_REGIME 选项
- [x] 2.3 在前端 ui-controls.js 中新增均值回归参数面板（RSI 周期、买卖阈值、最大持仓天数、止损百分比、regime MA）

## Phase 3: Docker 构建与验证

- [x] 3.1 Docker rebuild + 启动
- [x] 3.2 冒烟测试：API 调用 adaptive_regime 策略，验证返回结果包含正确的 reason_code 和 meta 字段
- [x] 3.3 对比测试：同参数下 sma_cross vs adaptive_regime，验证趋势期行为一致、震荡期有差异
