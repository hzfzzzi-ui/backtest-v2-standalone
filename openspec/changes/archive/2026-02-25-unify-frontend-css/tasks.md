## 1. 审计：确认实际使用的样式

- [x] 1.1 Grep index.html 和 backtest_v2.js 中所有 CSS class 名，生成完整清单
- [x] 1.2 Grep backtest_v2.js 中所有 `var(--` CSS 变量引用，确认需要保留的 token 名
- [x] 1.3 标记 style.css 中哪些规则被实际使用、哪些是废代码

## 2. 创建 workbench.css — Token 与 Reset

- [x] 2.1 创建 `frontend/assets/css/workbench.css`，写入文件头注释
- [x] 2.2 写入统一的 `:root` token 定义（采用 `--wb-*` 命名空间，合并后的色板值）
- [x] 2.3 写入 Reset 块（box-sizing, body, a, scrollbar 全局样式）

## 3. 创建 workbench.css — 基础组件

- [x] 3.1 写入 `.formInput`, `.formLabel` 规则（从 style.css 提取，去掉 hover-jump）
- [x] 3.2 写入 `.pill` 规则（从 style.css 提取，去掉 ripple/uppercase/hover-jump）
- [x] 3.3 写入 `.card` 规则（从 style.css 提取，去掉 hover 动画和 fadeIn）
- [x] 3.4 写入 `.btn` 规则（如被使用）
- [x] 3.5 写入 table 基础规则（从 backtest_v2.css 的 `.wb-table` 为准，无 zebra/uppercase）
- [x] 3.6 写入工具类（`.mono`, `.muted`, `.up`, `.down`, `.num`, `.wb-inline`, `.wb-mini`, `.wb-code`）

## 4. 创建 workbench.css — 工作台布局

- [x] 4.1 写入 App Shell（`.wb-app`, `.wb-command`, `.wb-body`）
- [x] 4.2 写入 Icon Rail（`.wb-rail`, `.wb-rail-btn`）
- [x] 4.3 写入 Drawer（`.wb-drawer`, `.wb-acc`, `.wb-subacc`, `.wb-module`, `.wb-field` 等）
- [x] 4.4 写入 Main Content（`.wb-main`, `.wb-main-content`, `.wb-kpi-row`, `.wb-kpi`）
- [x] 4.5 写入 Chart Canvas（`.wb-canvas`, `.wb-chart`）
- [x] 4.6 写入 Bottom Dock（`.wb-dock`, `.wb-dock-tabs`, `.wb-dock-panel`, `.wb-table-wrap`, `.wb-log`）
- [x] 4.7 写入 Status Panel（`.wb-status-panel`）
- [x] 4.8 写入 Empty & Loading states（`.wb-empty`, `.wb-skeleton`）

## 5. 创建 workbench.css — 动画与响应式

- [x] 5.1 写入 `@keyframes`（pulse, spin, wb-shimmer）
- [x] 5.2 写入所有 `@media` 响应式断点规则
- [x] 5.3 写入滚动条样式（workbench 各区域）

## 6. 更新 HTML 引用

- [x] 6.1 更新 `frontend/index.html`：两个 `<link>` 替换为单个引用 `workbench.css`

## 7. 删除旧文件

- [x] 7.1 删除 `frontend/assets/css/style.css`
- [x] 7.2 删除 `frontend/assets/css/backtest_v2.css`

## 8. 验证

- [x] 8.1 Grep 确认 workbench.css 中无未前缀的 token 定义（`--bg:`, `--accent:` 等）
- [x] 8.2 Grep 确认无 override 模式（`.wb-app table`, `.wb-app .pill` 等选择器）
- [x] 8.3 Grep 确认审计清单中所有 class 名在 workbench.css 中都有对应规则
- [x] 8.4 Docker 重建并验证页面正常显示
