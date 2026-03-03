# Tasks: three-layer-regime-filter

## Phase 1: 基础计算模块

- [x] 1.1 在 `features.py` 中实现 `adx_matrix(high, low, close, period)` 函数，支持 T×N 和 T 维输入，Wilder 平滑，逐列计算
- [x] 1.2 在 `ingest_universe.py` 中新增 `SW_L1_INDEX_MAP` 常量（industry_l1 名称 → 801xxx.SI 代码映射，31 个行业全覆盖）

## Phase 2: 数据加载层

- [x] 2.1 在 `pg_provider.py` 中新增 `load_sector_indices(start_date, end_date)` 方法，从 pit_index_daily 加载所有 801xxx.SI 行业指数 OHLCV 数据
- [x] 2.2 在 `pg_provider.py` 中新增 `load_industry_mapping(symbols)` 方法，从 pit_industry_history 加载 PIT-safe 股票→行业 L1 映射
- [x] 2.3 在 `provider.py` 基类中添加对应的抽象方法签名

## Phase 3: RegimeFilter 核心模块

- [x] 3.1 创建 `backend/core/engine_vector/regime_filter.py`，实现 `RegimeFilterConfig` 数据类（所有参数含默认值）
- [x] 3.2 实现 RegimeFilter 单层计算管线：`_compute_layer_gate(close_matrix, high_matrix, low_matrix, alpha, config)` → 从原始价格到 sigmoid 门控的完整流程（EMA slope → spread → ADX → trend_score → z-score → EMA smooth → sigmoid）
- [x] 3.3 实现 `RegimeFilter.precompute()` 方法：构建 Market/Sector/Stock 三层门控矩阵 + 行业映射展开 + 三层乘法复合 → `regime_signals[T, N]`
- [x] 3.4 实现行业数据缺失降级逻辑：行业指数无数据时 G_sec = 1.0，无行业映射时 G_sec = 1.0
- [x] 3.5 实现诊断属性 `diagnostics`：gate_m_mean、gate_sec_coverage、regime_signal_mean、regime_signal_above_threshold_pct、precompute_seconds

## Phase 4: 集成到引擎

- [x] 4.1 在 `experiment_runner.py` 中加载行业指数和行业映射数据，通过 kwargs 传递到 portfolio_builder
- [x] 4.2 在 `portfolio_builder.py` 和 `portfolio_simulator_strict.py` 中透传 sector_data 和 industry_map 参数
- [x] 4.3 修改 `RegimeRouterSignalProvider.precompute()`：当检测到 `regime_filter` 配置时，创建 RegimeFilter 实例并调用 precompute，用 regime_signals 阈值生成 `regime_on[T, N]` 矩阵
- [x] 4.4 修改 `RegimeRouterSignalProvider.day_signals()`：将全局 `regime_on[i]` 改为逐股票 `regime_on[i, col]` 过滤买入候选
- [x] 4.5 将 RegimeFilter 诊断数据合并到 provider 的诊断计数器中

## Phase 5: 配置与兼容性

- [x] 5.1 在 `models.py` 中新增 `RegimeFilterConfig` Pydantic model，在策略配置中作为可选字段
- [x] 5.2 创建测试配置 `configs/sweep/r3_regime_filter_csi800.json`，启用 RegimeFilter + trailonly ATR（使用最佳参数）
- [x] 5.3 验证无 RegimeFilter 配置时完全退回旧逻辑（结果零差异）

## Phase 6: 验证与实验

- [x] 6.1 Docker rebuild + 运行 RegimeFilter 配置回测，验证产物正常输出
- [x] 6.2 对比实验：RegimeFilter ON vs OFF，记录 Sharpe、Return、MaxDD、trade count、win rate
