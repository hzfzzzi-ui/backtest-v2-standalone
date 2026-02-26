## Context

当前前端有两套 CSS 文件：
- `style.css`（872行）— "PAMS Design System"，包含大量未使用的组件样式和具有全局副作用的规则
- `backtest_v2.css`（606行）— "Strategy Workbench"，定义工作台布局，同时包含约 40 行用于覆盖 style.css 副作用的代码

两文件各自定义了一套 CSS custom properties（`--bg/*` vs `--wb-*`），色值、圆角、间距均有微妙差异，导致视觉不统一。

## Goals / Non-Goals

**Goals:**
- 合并为单一 `workbench.css`，消除双 token 体系
- 删除所有未使用的 PAMS 组件样式（statusbar、nav、FX、cashflow、holdings、alerts 等）
- 删除所有 override/undo 代码块
- 统一圆角（3 档）、间距（8px 基线）、字体层级
- 保持所有现有 CSS class 名称不变，确保 JS 零改动
- 视觉微调提升专业感

**Non-Goals:**
- 不重写 HTML 结构（class 名不变）
- 不修改任何 JavaScript 逻辑
- 不引入 CSS 预处理器或构建工具链
- 不改变响应式断点策略
- 不重新设计整体布局（rail + drawer + main + dock 架构保持不变）

## Decisions

### Decision 1: 合并为单文件 workbench.css

**选择**: 将 style.css 和 backtest_v2.css 合并为 `workbench.css`
**备选**: 保留两文件但精简 style.css → 仍有 drift 风险
**理由**: 本项目是独立部署，无其他页面依赖 style.css 的 PAMS 组件。单文件消除所有冲突源头，维护成本最低。

### Decision 2: 统一使用 `--wb-*` token 命名空间

**选择**: 保留 `--wb-*` 前缀作为唯一 token 命名空间
**备选**: 去掉前缀用更短的 `--bg`、`--accent` → 缺乏命名空间隔离
**理由**: `--wb-*` 已在 HTML 中被大量引用，保留可减少改动量。前缀能防止与未来可能的第三方库冲突。

### Decision 3: 从 style.css 提取的保留部分

仅保留以下被实际使用的规则：
1. **Reset**: `box-sizing`, `html/body` height, `body` margin/font/background/color, `a` 样式
2. **基础组件**: `.formInput`, `.formLabel`, `.pill`（去掉 ripple/uppercase/hover-jump）, `.card`（去掉 hover 动画）
3. **工具类**: `.mono`, `.muted`, `.up`, `.down`, `.num`
4. **动画**: `@keyframes pulse`, `spin`（被 JS 引用）

删除以下未使用部分：
- `.statusbar`, `.nav`, `.topbar`, `.brand`
- `.dashRow1`, `.kpiGroup`, `.fxCard`, `.fxRow` 等 FX 相关
- `.cashflowList`, `.txRow`, `.txAmt` 等 cashflow 相关
- `.analysisList`, `.analysisRow` 等 holdings 相关
- `.alertStrip`, `.alertItem`, `.alert`
- `.month-selector`
- `.funnel`, `.candidate-row`, `.trail`, `.detail-grid`
- `.flow-guide`, `.flow-steps`, `.event-row`
- `.align-row`, `.gauge-bar`
- `#cardPerf::before` 等 ID 选择器增强
- `#runStatus`, `#validationSummary` shimmer 动画
- `#tabSummary`, `#tabDrill` 下划线增强
- `.card h4::before` 蓝色竖线装饰
- `button.pill[style*="background:var(--good)"]` 等属性选择器增强

### Decision 4: 统一设计 token

| Token | 当前 style.css | 当前 backtest_v2.css | 统一后 |
|-------|---------------|---------------------|--------|
| 背景 | `#0b0e11` | `#0f131a` | `#0f131a` (偏深蓝更专业) |
| 表面 | `#111418` | `#151c26` | `#151c26` |
| 边框 | `#252a31` | `#283346` | `#283346` |
| 文字 | `#e1e4e8` | `#dde7f3` | `#dde7f3` |
| 强调 | `#58a6ff` | `#52a8ff` | `#52a8ff` |
| 绿 | `#3fb950` | `#56c585` | `#56c585` |
| 红 | `#f85149` | `#ff6d75` | `#ff6d75` |
| 黄 | `#d29922` | `#efba56` | `#efba56` |
| 圆角 | 4/6/8px | 10/14px | 6/10/14px (3档) |

统一采用 backtest_v2.css 的色板，因为这是用户实际看到的主色调。

### Decision 5: 文件内部结构

```
workbench.css
├── 0. 文件头注释
├── 1. Token 定义 (:root)
├── 2. Reset (box-sizing, body, a, scrollbar)
├── 3. 基础组件 (formInput, formLabel, pill, card, btn, table)
├── 4. 工具类 (mono, muted, up, down, num, inline, mini, code)
├── 5. App Shell (wb-app, wb-command, wb-body)
├── 6. Icon Rail
├── 7. Drawer (accordion, module, field)
├── 8. Main Content (kpi-row, canvas, chart)
├── 9. Bottom Dock (tabs, panels, table, log)
├── 10. Status Panel (overlay)
├── 11. Empty & Loading states
├── 12. Scrollbars
├── 13. Animations (@keyframes)
└── 14. Responsive (@media)
```

## Risks / Trade-offs

- **[风险] 遗漏被使用的样式** → 通过 grep HTML/JS 中所有 class 名逐一确认；合并后 Docker 重建验证
- **[风险] JS 中有 inline style 引用 CSS 变量** → grep `var(--` 确认所有引用的变量名都保留
- **[权衡] 单文件较长（预计 ~800行）** → 可接受，通过清晰的分段注释保持可读性；比当前 1478 行双文件已大幅精简
