## Why

G5 配置（EMA8/25 + TP30% + trail k=6 + min5/cool5）的 walk-forward 测试显示：10 个 1 年窗口中仅 5/10 正收益（avg CAGR=2.8%，std=18.9%），收益高度集中在牛市年（2020: +46.4%），震荡/熊市年亏损严重（2017: -19.0%，2019: -15.9%）。之前尝试的 benchmark EMA20/60 regime filter 因滞后问题反而让 CAGR 从 +7.10% 变为 -2.07%。

核心问题：**固定 max_positions=10 在市场状态变化时不够灵活**——牛市应多持仓捕获更多 alpha，熊市/震荡市应缩仓减少损耗。需要一种低滞后、不砍牛市利润的动态仓位调节机制。

## What Changes

- **新增横截面扩散（Breadth/Dispersion）计算模块**：每个交易日基于全 universe 可交易股票计算三类 score（上涨比例 breadth_up、动量扩散 breadth_momo、收益离散度 dispersion），向量化预计算
- **新增动态仓位映射函数**：将 score 映射为当日 max_positions（阶梯版 3/10/15，平滑版 3~15 线性），替代固定常量
- **引擎 _run_unified_loop 改造**：max_positions 从固定 int 改为 per-day 数组；当持仓 > 当日上限时按弱势优先 forced sell
- **不改变 G5 信号生成与退出逻辑**：EMA cross / TP / ATR stop / trail / min_hold / cooldown 全部保持不变
- **实验框架**：6 组指标×映射组合 + baseline 对照，跑 10 年全区间 + 10 个 1 年 walk-forward 窗口

## Capabilities

### New Capabilities
- `breadth-score-engine`: 横截面 breadth/dispersion score 计算引擎——基于 universe 内可交易股票的日收益统计，输出每日 score (0~1)
- `dynamic-max-positions`: 动态仓位上限机制——将 breadth score 映射为当日 max_positions，支持阶梯和平滑两种映射模式

### Modified Capabilities
（无现有 spec 层级的需求变更）

## Impact

**后端核心改动**：
- `backend/core/config/models.py` — 新增 `BreadthConfig` dataclass
- `backend/core/config/loader.py` — 加载 breadth config
- `backend/core/engine_vector/breadth.py` — **新建**，向量化 score 计算 + dynamic maxpos 映射
- `backend/core/engine_vector/portfolio_simulator_strict.py` — `_run_unified_loop` 动态 max_positions + forced sell
- `backend/core/tools/experiment_runner.py` — 透传 breadth_cfg
- `backend/core/portfolio/portfolio_builder.py` — 透传 breadth_cfg
- `backend/api/endpoints/_experiment_runner_api.py` — API 透传

**前端改动（可后补）**：
- `frontend/index.html` — Position & Risk 面板新增 breadth 控件区 (~15 行 HTML)
- `frontend/assets/js/ui-controls.js` — config draft 收集 + 回填 (~15 行 JS)
- `frontend/assets/js/report.js` — 诊断统计展示 (~5 行 JS)

**产物增量**：
- `perf.json` 新增字段：`avg_dynamic_maxpos`、`breadth_score_mean`、`forced_sell_count`、`breadth_allow_days`/`breadth_restrict_days`
- 诊断：daily_rows 中记录当日 breadth_score 和 dynamic_maxpos

**无 breaking changes**——breadth.enabled=false（默认）时行为与现有完全一致。
