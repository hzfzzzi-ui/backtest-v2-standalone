## Why

当前前端 Drawer 只有 3 个功能面板（Universe / Signal+Composition / Risk&Exit），无法表达 V2 策略的 9 阶段决策流水线（Universe → Market → Industry → Stock Trend → Ranking → Entry → Portfolio → Risk → Exit）。具体问题：

1. **策略选择器缺失 Breakout/RSI**：`<select>` 只有 SMA_CROSS / EMA_CROSS，无法从 UI 配置 breakout_trend 或 rsi_reversal 策略。
2. **阶段混杂**：大盘环境(S2)、个股趋势(S4)、入场信号(S6) 全部塞在 Signal+Composition 面板里，层级不清。
3. **无法加载冠军配置**：breakout 冠军（CAGR +5.46%）只能通过脚本跑，无法从前端"加载"下拉直接调用。
4. **缺少 S3(行业门控) 和 S5(排序) 面板**：这两个阶段在后端已实现但前端无对应 UI。

## What Changes

- **Rail 从 5 个按钮扩展到 11 个**：S1-S9 + JSON + History
- **拆分 Signal+Composition** 为 S2(大盘环境)、S3(行业趋势)、S4(个股趋势)、S5(个股排序)、S6(入场信号) 五个独立面板
- **拆分 Risk&Exit** 为 S7(组合构建)、S8(风险控制)、S9(退出) 三个独立面板
- **S6 策略选择器**新增 BREAKOUT_TREND 和 RSI_REVERSAL 选项，并根据选择动态显示对应参数面板
- **删除 Composition Pipeline**（TBD 功能，不再需要）
- **注册冠军配置**：将 3.4 号 breakout 冠军和 EMA cross 冠军配置注册到 `outputs/configs/` 供前端"加载"下拉直接调用
- **`buildConfigDraft()` 重构**：支持生成 breakout_trend / rsi_reversal 策略的配置 JSON
- **`applyConfigToUI()` 重构**：支持从 breakout_trend / rsi_reversal 配置 JSON 回填 UI 控件

## Capabilities

### New Capabilities
- `9stage-drawer-layout`: 将前端 Drawer 从 3 功能面板重组为 9 阶段流水线布局（S1-S9 + JSON + History），每个阶段对应独立的 Rail 按钮和面板
- `breakout-entry-ui`: 前端 S6 入场信号面板支持 BREAKOUT_TREND 策略选择及参数配置（breakout_window, regime_ma, v2_trend_filter 等），以及 RSI_REVERSAL 均值回归策略选择
- `champion-config-presets`: 预置 3.4 号冠军策略配置（Breakout 冠军 + EMA Cross 冠军）为可加载的前端配置，支持从"加载"下拉直接调用

### Modified Capabilities
- `dual-tab-layout`: Rail 按钮从 5 个扩展到 11 个，面板路由逻辑更新
- `frontend-module-split`: `ui-controls.js` 中 `buildConfigDraft()` 和 `applyConfigToUI()` 需支持新策略类型

## Impact

- **前端文件**：`frontend/index.html`（HTML 重组）、`frontend/assets/js/ui-controls.js`（JS 逻辑重构）、`frontend/assets/css/workbench.css`（Rail 样式适配 11 个按钮）
- **配置文件**：新增 `backend/configs/champion_breakout_v2.json` 和 `backend/configs/champion_ema_cross_v2.json`
- **注册脚本**：修改或新增注册逻辑将冠军配置写入 `outputs/configs/`
- **后端 API**：无改动（已支持 breakout_trend 策略路由）
- **验证标准**：从前端加载冠军配置并运行，结果必须与 3.4 号脚本结果一致（Breakout CAGR +5.46%, MDD -24.32%）
