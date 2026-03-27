## ADDED Requirements

### Requirement: ETF研究入口必须为宽基主线提供三类研究 profile
当用户运行宽基 ETF 独立主线 study 时，研究入口 MUST 支持以下三类 profile：

- `absolute_filter_profile`
- `candidate_pool_profile`
- `selection_chain_profile`

研究入口 MUST 保证矩阵展开时每组实验只改一个主变量。

#### Scenario: 研究入口展开主瓶颈矩阵
- **WHEN** 用户运行宽基 ETF 主线瓶颈 study
- **THEN** 研究入口 MUST 能展开过滤族、候选池族和选择链路族
- **THEN** 每组实验 MUST 只切换对应的 profile，而不是同时混入其他变量

### Requirement: 本轮研究入口必须禁止行业ETF混入
本轮宽基 ETF 主线瓶颈 study MUST 只允许宽基 ETF 与宽基风格 proxy 参与。研究入口 SHALL NOT 接受行业 ETF、主题 ETF 或其他非宽基资产作为本轮正式候选池成员。

#### Scenario: 行业ETF被显式拒绝
- **WHEN** 用户尝试把行业 ETF 或主题 ETF 放入本轮宽基 ETF 主线瓶颈 study
- **THEN** 研究入口 MUST 返回显式错误或告警
- **THEN** 系统 SHALL NOT 静默把该资产纳入正式候选池

### Requirement: 标准池与proxy池比较必须显式暴露覆盖窗口
当研究入口比较 `proxy pool` 与 `standard pool` 时，系统 MUST 显式暴露 overlap 窗口，并 SHALL NOT 把不同覆盖长度的实验结果伪装成同一时间窗口下的可比结论。

#### Scenario: 标准池与proxy池使用overlap窗口
- **WHEN** 系统比较标准 ETF 与 proxy ETF 的候选池 profile
- **THEN** 研究入口 MUST 输出共同覆盖起止日期
- **THEN** compare 结果 MUST 使用该共同覆盖窗口
