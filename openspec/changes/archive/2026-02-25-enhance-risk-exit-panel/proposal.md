## Why

Risk & Exit 模块当前只是一组配置输入框，缺乏运行后的反馈信息。用户无法在配置面板中直接看到退出策略的生效证据、约束触发情况，以及 ATR 口径说明。控件之间也没有联动（未启用的功能输入框仍可编辑）。此外缺少组合级回撤风控、退出优先级配置和最小成交提示等高级功能。

## What Changes

### 必补（前端 + API 规范化）

- **退出触发统计**：Exit 区块下方显示 `reversal_exit_count` / `atr_stop_exit_count` / `atr_trail_exit_count` / `atr_trail_update_count` / `time_exit_count`，运行后从 results API 填充
- **ATR 口径说明**：Exit 区块内添加只读提示，显示 ATR 窗口（14日）、价格口径（前复权/后复权）、触发价口径（close vs next_open）
- **控件联动**：未勾选"移动止盈"时 `trail_k` 输入框置灰 + 标注单位（×ATR）；未勾选"时间退出"时 `N days` 输入框置灰
- **约束触发统计**：Position & Risk 下方显示 `avg_positions` / `slots_left` / `cap_hit_count`（单票/行业）/ `cash_skip_count` / `lot_skip_count`
- **API 规范化**：在现有 results 响应中补全缺失字段（`reversal_exit_count`、`time_exit_count`、`cap_hit_single`、`cap_hit_industry`、`slots_left`），统一 counter 命名

### 强烈建议（前端占位 + 配置 JSON 规范，后端引擎逻辑后续实现）

- **Risk Gate（组合级风控）**：新增区块，配置回撤阈值、动作（降档/停手）、冷却天数；显示触发次数
- **退出优先级**：Exit 区块内可配置同日多条件触发的优先级顺序（默认 stop_loss > reversal > time > trail）
- **最小成交提示**：Position & Risk 内按最近价格估算"买一手所需现金"，提示可能触发 SKIP_LOT_TOO_SMALL

## Capabilities

### New Capabilities
- `exit-stats-display`: Exit 区块触发统计展示 + ATR 口径说明 + 控件联动
- `constraint-stats-display`: Position & Risk 约束触发统计展示
- `risk-gate-config`: 组合级回撤风控配置（前端占位 + JSON 规范）
- `exit-priority-config`: 退出优先级配置（前端占位 + JSON 规范）
- `min-trade-hint`: 最小成交提示

### Modified Capabilities
_(无已有 spec 需要修改)_

## Impact

- `frontend/index.html` — Risk & Exit 模块 HTML 结构扩展
- `frontend/assets/css/workbench.css` — 新增统计展示、联动置灰样式
- `frontend/assets/js/backtest_v2.js` — 控件联动逻辑、统计数据填充、Risk Gate / Priority / Min-trade 占位逻辑
- `backend/api/endpoints/backtest_v2.py` — results 响应补全 `reversal_exit_count`、`time_exit_count`、`cap_hit_single`、`cap_hit_industry`、`slots_left`
- `backend/api/endpoints/backtest_v2_artifacts.py` — 产物读取同步补全
- 后端引擎层（`portfolio_simulator_strict.py` 等）— Risk Gate 和 Exit Priority 的实际引擎逻辑 **本次不改**，仅规范接口
