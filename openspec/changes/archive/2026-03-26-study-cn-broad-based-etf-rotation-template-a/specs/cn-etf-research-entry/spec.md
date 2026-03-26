## ADDED Requirements

### Requirement: cn_etf 研究入口必须提供模板 A 的 A0/A1 预设
`cn_etf` 研究入口 MUST 提供模板 A 的预设定义，并且 MUST 同时区分：

- `A0`：当前可直跑版
- `A1`：目标正式版

若 `A1` 所需标准资产尚未接通，研究入口 MUST 显式暴露其未就绪状态，而不是静默退回 A0。

#### Scenario: A0 预设可直接展开
- **WHEN** 用户选择模板 A 的 A0 预设
- **THEN** 系统 MUST 生成仅依赖当前已接通目录的研究配置

#### Scenario: A1 预设未就绪时显式提示
- **WHEN** 用户选择模板 A 的 A1 预设且标准资产未接通
- **THEN** 系统 MUST 返回显式未就绪提示或等价状态
- **THEN** 系统 SHALL NOT 静默回退到 A0

### Requirement: cn_etf 研究入口必须显式暴露模板 A 的 fallback 与成长位选择
当研究入口展开模板 A 时，配置摘要 MUST 显式暴露：

- fallback 类型
- 成长位选择
- `Top1` 还是 `Top2`
- 调仓频率

#### Scenario: 模板 A 配置摘要可读
- **WHEN** 用户查看模板 A 的研究配置摘要
- **THEN** 系统 MUST 能直接回答当前实验选择了哪种 fallback、哪一个成长位和哪种持仓数规则
