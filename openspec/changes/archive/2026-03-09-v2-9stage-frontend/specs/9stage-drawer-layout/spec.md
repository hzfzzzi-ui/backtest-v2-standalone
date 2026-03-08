# 9-Stage Drawer Layout

## 概述
将前端 Drawer 从 3 功能面板重组为 9 阶段流水线布局（S1-S9 + JSON + History），每个阶段对应独立的 Rail 按钮和面板。

## 需求

### R1: Rail 按钮
- Rail 区域包含 11 个按钮：S1-S9 + JSON + History
- S1-S9 按钮使用数字 badge（①-⑨）+ 单字标签：池/盘/业/股/排/入/组/控/出
- S1-S9 与 JSON/History 之间有视觉分隔线
- 点击任意按钮切换到对应面板，同时高亮当前按钮

### R2: 面板路由
- data-panel 值从 `universe/sigcomp/risk/json/history` 变为 `s1/s2/s3/s4/s5/s6/s7/s8/s9/json/history`
- 每个 panel 对应一个 `<section class="wb-module" data-module="sN">`
- 面板切换逻辑复用现有的 Rail click handler

### R3: HTML 重组规则
- **S1 (universe)**：原 `data-module="universe"` 改为 `data-module="s1"`，HTML 内容不变
- **S2 (market)**：从 sigcomp 提取市况判断面板（wbRegimePanel 及其子元素）
- **S3 (industry)**：新建面板，包含行业门控参数（enable, rank_window, top_pct）
- **S4 (stock trend)**：从 sigcomp 提取入场趋势过滤块（wbEntryFilterBlock 及其子元素），改为独立面板
- **S5 (ranking)**：新建面板，包含动量排序参数（momentum_top_pct）
- **S6 (entry)**：保留策略选择器 + 趋势模式参数 + 震荡模式参数，删除 Composition Pipeline
- **S7 (portfolio)**：从 risk 提取 Position & Risk 面板中的持仓部分（max_positions, lot, cap, sizing）
- **S8 (risk)**：从 risk 提取风控部分（DD 熔断, MA200 过滤, ATR 止损倍数）
- **S9 (exit)**：原 Exit 面板改为独立面板

### R4: CSS 适配
- Rail 内 11 个按钮需要缩小间距以适应垂直空间
- S1-S9 按钮可使用纯文字 + 数字样式（无需 SVG 图标）
- 保持 Drawer 宽度 340px 不变

### R5: Drawer 标题联动
- 切换到 S1-S9 时，Drawer 顶部标题显示对应阶段名称（如"S2 大盘环境"）
- JSON 和 History 标题保持现有行为
