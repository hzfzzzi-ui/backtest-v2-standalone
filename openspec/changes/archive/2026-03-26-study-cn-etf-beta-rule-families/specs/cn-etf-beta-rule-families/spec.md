## ADDED Requirements

### Requirement: ETF beta 规则族研究必须限定为三组正式路线
系统 MUST 将 `cn_etf_beta` 的下一阶段正式研究范围限定为以下三组规则族：
- `Dual Momentum 基础版`
- `Dual Momentum + 缓冲带`
- `Dual Momentum + Vol Target`

系统 SHALL NOT 在未完成上述三组规则族比较前，把“继续扩 ETF 候选池”作为默认优先研究方向。

#### Scenario: 创建 ETF 规则族研究计划
- **WHEN** 系统为 `cn_etf_beta` 创建新的正式研究计划
- **THEN** 研究计划 MUST 明确属于上述三组规则族之一
- **THEN** 研究计划 SHALL NOT 仅以单个窗口参数微调作为主目标

### Requirement: ETF 规则族研究必须使用受控候选池和统一 fallback
系统 MUST 将 ETF 规则族研究的主候选池限定为 `510300` 和 `510050`。

系统 MAY 允许 `511010` 作为最小防守 fallback 或现金代理对照，但 SHALL NOT 在本轮正式规则族研究中把 `510500`、`512100`、`512890` 作为主候选。

#### Scenario: 研究使用正式主候选池
- **WHEN** 系统执行 ETF 规则族主研究
- **THEN** 主候选池 MUST 只包含 `510300` 和 `510050`
- **THEN** fallback MUST 明确标记为 `511010` 或现金代理

### Requirement: ETF 规则族研究必须定义最小 AB 方案
每组 ETF 规则族 MUST 明确定义最小 AB 方案，至少包含：
- 对照组
- 主改动
- 固定窗口
- 固定候选池
- 固定防守 fallback 口径

#### Scenario: 规则族研究具备最小 AB 结构
- **WHEN** 系统登记一组 ETF 规则族实验
- **THEN** 实验定义 MUST 能清楚区分对照组与主改动
- **THEN** 实验定义 MUST 能回答“这轮究竟在比什么”
