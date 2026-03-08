## MODIFIED Requirements

### Requirement: 顶部 Tab 切换
右侧结果区 MAY 保留内部实现上的 tab 结构，但用户可见的结果浏览入口 SHALL 以单一结果页为主，不再要求用户先在 [概览] / [分析] 之间切换才能完成核心结果浏览。

#### Scenario: 结果页默认直达核心结果
- **WHEN** 页面加载或回测完成
- **THEN** 系统 SHALL 直接显示核心结果页
- **THEN** 用户无需先切换到单独的“分析”Tab 才能查看漏斗、交易明细或日志入口

### Requirement: 概览 Tab 内容
结果页 SHALL 包含以下核心区块，并占据主工作区的主要阅读路径：
- 8 个 KPI 卡片
- NAV 主图
- 个股筛选 NAV
- 折叠诊断区

系统 MUST NOT 再把独立回撤图作为结果页固定主区块。

#### Scenario: 核心区块顺序固定
- **WHEN** 结果页渲染
- **THEN** 页面 SHALL 依次显示 KPI 卡片、NAV 主图、个股筛选 NAV、折叠诊断区
- **THEN** 页面 MUST NOT 再固定展示独立回撤图块

### Requirement: 分析 Tab 内容
原有分析能力 SHALL 收敛为中文折叠区：
- 买入漏斗
- 卖出漏斗
- 交易明细
- 日志

系统 MUST 移除 `Explain` 作为用户可见主入口。

#### Scenario: Explain 被移除
- **WHEN** 用户查看结果页诊断区
- **THEN** 页面 MUST NOT 再出现 `Explain` 英文标签作为主入口
- **THEN** 页面 SHALL 使用中文折叠区替代

#### Scenario: 交易明细与日志保留
- **WHEN** 用户展开诊断区
- **THEN** 页面 SHALL 继续提供交易明细与日志内容
- **THEN** 交易明细与日志 SHALL 可独立展开与收起
