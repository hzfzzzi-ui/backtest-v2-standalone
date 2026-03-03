# dual-tab-layout Specification

## Purpose
右侧主面板双 Tab 布局，将上下分割的 content+dock 结构改为 [概览] [分析] 两个全高 Tab 页面。

## Requirements

### Requirement: 顶部 Tab 切换
右侧主面板 SHALL 在顶部提供 Tab Bar，包含 [概览] 和 [分析] 两个 Tab。

#### Scenario: 默认显示概览
- **WHEN** 页面加载或回测完成
- **THEN** 系统 SHALL 默认激活"概览" Tab

#### Scenario: Tab 切换
- **WHEN** 用户点击 Tab 按钮
- **THEN** 系统 SHALL 显示对应 Tab 内容，隐藏其他 Tab 内容
- **THEN** 激活态 Tab 按钮 SHALL 显示蓝色下划线

### Requirement: 概览 Tab 内容
概览 Tab SHALL 包含原主面板的全部内容，占据 Tab Bar 以下全部可用高度。

#### Scenario: 概览布局
- **WHEN** 概览 Tab 激活
- **THEN** SHALL 依次显示：Summary Bar → KPI 卡片行 → 个股绩效表 → NAV 图表 → 回撤图表
- **THEN** 内容区 SHALL 可垂直滚动

### Requirement: 分析 Tab 内容
分析 Tab SHALL 包含原底部 Dock 的全部内容，提升为全高面板。

#### Scenario: 分析子标签
- **WHEN** 分析 Tab 激活
- **THEN** SHALL 显示 [Explain] [Execution] [Logs] 三个子标签
- **THEN** 默认激活 Explain 子标签

#### Scenario: 分析面板全高
- **WHEN** 分析 Tab 中任一子标签激活
- **THEN** 子面板内容 SHALL 占据 Tab Bar + 子标签栏以下全部可用高度
- **THEN** 子面板 SHALL 可垂直滚动，无 max-height 限制

### Requirement: 移除底部 Dock
系统 SHALL 不再显示固定高度的底部 Dock 区域。

#### Scenario: Dock 移除
- **WHEN** 页面渲染
- **THEN** SHALL 不存在 `wb-dock` 固定区域
- **THEN** SHALL 不存在 Dock 拖拽调整手柄
