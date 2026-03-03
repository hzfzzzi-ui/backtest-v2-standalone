## Tasks

### Bug 1: 持仓估值修复

- [x] `mapping.py:118` — adj_factor NULL 处理改为 `groupby("symbol").ffill().fillna(1.0)`
- [x] `ExitConfig` (models.py) — 新增 `atr_stop_k: float = 2.0` 字段（为 task 排序需要，先加字段再改 loader）
- [x] `_build_price_indices` (portfolio_simulator_strict.py:33-47) — 新增 `hfq_df` 参数，返回 `(open_idx, raw_close_idx, hfq_close_idx, adj_factor_idx)` 四元组
- [x] `compute_nav_snapshot` (portfolio_builder.py:38-53) — 新增 `hfq_close_idx` + `position_entry_adj` 参数，使用归一化公式 `qty × hfq_close / entry_adj` 消除价格空间不一致
- [x] `_run_unified_loop` (portfolio_simulator_strict.py:168) — 拆分 `close_idx`，新增除权除息持仓股数调整（adj_factor 变化时按比例调整 qty + avg_cost + entry_adj）
- [x] 入口函数 `run_portfolio_backtest` (portfolio_simulator_strict.py:767-769) — 同时用 raw_history 和 history(hfq) 调用 `_build_price_indices`，将两套索引传入三条路径
- [x] 三条路径 `_run_sma_path` / `_run_generic_path` / `_run_regime_router_path` — 适配新的 `raw_close_idx` + `hfq_close_idx` 参数签名，传递到 `_run_unified_loop`

### Bug 2: atr_stop_k 配置修复

- [x] `loader.py:76-77` — 从过滤列表移除 `"atr_stop_k"`
- [x] 三条路径中 `atr_stop_k` 取值逻辑改为：`exit_cfg.atr_stop_k if exit_cfg.atr_stop_k != 2.0 else _rb.atr_stop_k`

### 验证

- [x] Docker rebuild + 运行回测，确认 sz002252 除权日前后 NAV 无虚假跳变（9/17 split: NAV 106,292→104,738, -1.5% 正常波动；sell qty 从 600 正确调整为 1200）
- [x] 确认 atr_stop_k 修改在前端可生效（exit.atr_stop_k=1.5 → 引擎 resolved 值为 1.5，loader 不再过滤，API 透传正确）
