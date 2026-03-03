## ADDED Requirements

### Requirement: 未实现功能控件标注 TBD
前端工作台中后端未实现的功能控件 SHALL 在标签文字后追加灰色 `(TBD)` 标记，使用户清晰识别该功能尚未生效。

#### Scenario: 选股范围区域 TBD 控件
- **WHEN** 工作台渲染选股范围面板
- **THEN** 以下控件标签 SHALL 追加 `(TBD)` 标记：日均成交额下限、价格区间（最低价/最高价）、ATR 波动区间、涨跌停规则、行业过滤（模式+列表）、成分基准（动态/固定）

#### Scenario: 信号生成区域 TBD 控件
- **WHEN** 工作台渲染信号生成面板
- **THEN** 以下控件标签 SHALL 追加 `(TBD)` 标记：入场趋势过滤（close > 慢线）、入场斜率过滤、复合信号模块区域、实时预览区域

#### Scenario: 退出规则区域 TBD 控件
- **WHEN** 工作台渲染退出规则面板
- **THEN** 退出优先级排序区域 SHALL 保留已有的"即将支持"badge

#### Scenario: 仓位风控区域 TBD 控件
- **WHEN** 工作台渲染仓位与风控面板
- **THEN** 以下控件标签 SHALL 追加 `(TBD)` 标记：单票仓位上限、行业仓位上限
- **THEN** 现金不足策略的"缩量下单"选项 SHALL 追加 `(TBD)` 标记

#### Scenario: 成交价口径硬编码标注
- **WHEN** 工作台渲染成交价口径选择器
- **THEN** 该控件 SHALL 标注 `(仅 next_open)` 表明后端固定使用次日开盘价撮合

### Requirement: TBD 标记视觉规范
TBD 标记 SHALL 使用统一的视觉风格，不引入额外 CSS class。

#### Scenario: TBD 标记外观
- **WHEN** 控件标签包含 TBD 标记
- **THEN** `(TBD)` 文字 SHALL 使用灰色（#999 或同等浅色）、与标签文字同行显示
- **THEN** 控件本身 SHALL 保持可交互状态（不 disabled），以便用户了解默认值和功能规划
