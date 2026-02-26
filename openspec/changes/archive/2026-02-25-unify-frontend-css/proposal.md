## Why

前端使用两套互相冲突的 CSS 体系（style.css "PAMS Design System" + backtest_v2.css "Strategy Workbench"），导致：
- 两套色板微妙不同（`#0b0e11` vs `#0f131a`、`#58a6ff` vs `#52a8ff`）
- backtest_v2.css 中 ~40 行纯粹在覆盖 style.css 的全局副作用（uppercase、ripple、hover-jump、zebra）
- style.css 约 60% 是未使用的 PAMS 组件样式（statusbar、nav、FX、cashflow、holdings 等）
- 圆角体系冲突（4/6/8px vs 10/14px）

需要合并为单一 CSS 文件，消除冲突，提升视觉统一性和专业感。

## What Changes

- **删除** `frontend/assets/css/style.css`，从中提取仅被实际使用的 reset + 基础组件样式（~120行）
- **合并** 提取的基础样式与 `frontend/assets/css/backtest_v2.css` 为新的 `frontend/assets/css/workbench.css`
- **统一** 所有 CSS custom properties 为 `--wb-*` 命名空间，消除双色板
- **删除** backtest_v2.css 中所有 `.wb-app xxx { undo... }` 覆盖块
- **删除** style.css 中未使用的组件样式（statusbar、nav、FX、cashflow、holdings、alerts、month-selector 等）
- **统一** 圆角、间距、字体层级体系
- **更新** `frontend/index.html` 的 CSS 引用（两个 link → 一个）
- **视觉微调**：统一圆角体系、加强背景层级感、优化表格行间距、改善空状态展示

## Capabilities

### New Capabilities
- `unified-css`: 合并后的单一 CSS 设计体系，统一 token、消除覆盖、删除废代码

### Modified Capabilities
_(无已有 spec 需要修改)_

## Impact

- `frontend/assets/css/style.css` — 删除
- `frontend/assets/css/backtest_v2.css` — 删除
- `frontend/assets/css/workbench.css` — 新建（合并后）
- `frontend/index.html` — 更新 `<link>` 引用
- 后端无影响，JS 无影响（CSS class 名不变）
