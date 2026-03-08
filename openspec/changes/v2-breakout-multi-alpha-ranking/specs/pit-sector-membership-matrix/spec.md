## ADDED Requirements

### Requirement: 行业归属加载必须支持 PIT-safe 日级矩阵
系统 SHALL 提供按 `symbols + start + end` 加载 `pit_industry_history` 的接口，并构造按交易日对齐的股票-行业日级矩阵，供行业强度与行业相对强弱评分使用。

#### Scenario: 历史行业切换按时点生效
- **WHEN** 某股票在历史上发生行业切换
- **THEN** 系统 MUST 在切换日前后返回不同的行业归属
- **THEN** 不得在切换日前使用切换后的行业标签

#### Scenario: 无行业记录时返回空值
- **WHEN** 某股票在给定区间内没有行业历史记录
- **THEN** 日级行业矩阵中该股票对应值 MUST 为缺失
- **THEN** 上层排序逻辑 MUST 明确处理该缺失，而不是回填未来行业

### Requirement: 行业强度分数必须基于 PIT-safe 行业归属与行业指数
系统 SHALL 使用当日可见的股票-行业归属和行业指数历史，计算行业强度分数。

#### Scenario: 行业强度只用当日可见数据
- **WHEN** 计算交易日 `t` 的 `sector_strength_score`
- **THEN** 股票所属行业 MUST 来自交易日 `t` 的行业归属
- **THEN** 行业收益或行业均线状态 MUST 仅使用截至 `t` 日的行业指数数据

#### Scenario: 行业数据不足时不制造伪强度
- **WHEN** 某行业在交易日 `t` 缺少足够的历史窗口
- **THEN** `sector_strength_score` MUST 为空或退化为中性值
- **THEN** 不得用未来行业指数历史回填
