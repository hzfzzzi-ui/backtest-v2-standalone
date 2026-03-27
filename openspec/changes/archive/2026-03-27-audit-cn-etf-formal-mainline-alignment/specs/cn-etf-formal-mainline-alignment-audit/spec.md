## ADDED Requirements

### Requirement: ETF Phase 1 必须存在正式口径对齐审计
系统 MUST 以根目录正式策略文档 [A股ETF子系统策略思路md](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/A股ETF子系统策略思路md) 作为 `cn_etf_beta` Phase 1 的唯一正式口径来源，并为 ETF runtime profile、study 与实验结果提供正式口径对齐审计。

#### Scenario: 正式口径对齐审计存在唯一真相源
- **WHEN** 系统评估某条 ETF runtime profile、study 或实验结果是否属于 Phase 1 正式主线
- **THEN** 系统 MUST 以根目录正式策略文档为唯一正式口径来源
- **THEN** 系统 SHALL NOT 以当前最优研究结果或历史实验名称反推正式定义

### Requirement: ETF 运行结果必须被显式分类为正式主线或研究分支
系统 MUST 为每条 ETF runtime profile、study 与实验结果输出显式分类，至少包括：
- `formal_mainline`
- `research_only`
- `do_not_promote`

该分类 MUST 能进入 `run_meta`、`audit` 或等价正式产物，而不是只存在于文件命名或人工说明中。

#### Scenario: 正式主线实验被显式标注
- **WHEN** 某条 ETF 运行路径符合 Phase 1 正式文档的资产池、limited defense 与职责边界
- **THEN** 系统 MUST 将其分类为 `formal_mainline`

#### Scenario: 研究分支实验被显式降级
- **WHEN** 某条 ETF 运行路径使用了超范围资产、研究型信号语义或越界输出 contract
- **THEN** 系统 MUST 将其分类为 `research_only` 或 `do_not_promote`

### Requirement: ETF 正式口径偏离必须输出可审计原因
系统 MUST 为 ETF 正式口径偏离输出最小可审计 reason codes，至少覆盖：
- 超范围资产
- 超范围 limited defense candidate
- 信号语义越界
- 输出 contract 越界
- Governor 边界越界

#### Scenario: 超范围资产导致降级
- **WHEN** 某条 ETF 路径使用 `511010.SH`、`588000.SH`、`159915.SZ`、`518880.SH` 或其他正式文档明确排除的资产作为正式主线路径的一部分
- **THEN** 系统 MUST 输出显式偏离原因
- **THEN** 系统 MUST 将该路径降级为 `research_only` 或 `do_not_promote`

#### Scenario: 偏离原因可进入研究审计
- **WHEN** 用户查看 ETF 实验的 research audit
- **THEN** 审计结果 MUST 能回答该实验为什么不是正式主线
- **THEN** 审计结果 MUST 能引用正式偏离原因而不是仅输出抽象状态
