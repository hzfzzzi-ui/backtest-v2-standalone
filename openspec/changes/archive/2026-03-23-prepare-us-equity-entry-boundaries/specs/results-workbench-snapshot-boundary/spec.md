## ADDED Requirements

### Requirement: 桌面页壳必须按 `assetContext` 驱动品牌与提示文案
系统 MUST 让桌面页壳的品牌标题、资产提示和 A 股专有说明从 `assetContext` 派生，而 SHALL NOT 再把 “A股回测研究台” 作为无条件全局文案。

#### Scenario: 渲染 A 股实验
- **WHEN** snapshot `assetContext.asset_scope='cn_a_equity'`
- **THEN** 页壳 MAY 展示 A 股专有品牌和提示
- **THEN** A 股 universe/成分口径文案 MUST 保持当前行为

#### Scenario: 渲染美股个股实验或配置
- **WHEN** snapshot 或配置 `assetContext.asset_scope='us_equity'`
- **THEN** 页壳 MUST 显示非 A 股品牌或“入口准备中”提示
- **THEN** 页壳 SHALL NOT 继续把 A 股股票池和成分口径文案当成默认真相

### Requirement: 前端 fallback 不得继续把空资产上下文强制写成 `cn_a_equity`
系统 MUST 让前端 fallback 优先读取 config draft、manifest、surface 和 loaded source 中的资产上下文。前端 SHALL NOT 在缺少这些来源时直接把 `cn_a_equity` 写成唯一通用 fallback。

#### Scenario: 加载旧 A 股实验
- **WHEN** 历史实验只在 manifest 或 config 中携带 A 股资产上下文
- **THEN** 前端 MUST 通过这些已有来源恢复 `cn_a_equity`
- **THEN** 前端 SHALL NOT 因为空壳 fallback 逻辑而改变实验资产语义
