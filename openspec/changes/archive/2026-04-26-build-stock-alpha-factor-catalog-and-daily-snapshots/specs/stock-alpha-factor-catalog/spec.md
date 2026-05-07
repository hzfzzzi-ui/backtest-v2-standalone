## ADDED Requirements

### Requirement: 个股 alpha 因子目录必须成为正式单一真相

系统 MUST 为个股 alpha 原子因子维护正式 `factor_catalog`，并把因子标识、中文说明、数据依赖、计算频率、as-of 约束、标准化约定和可解释边界作为正式合同管理。

#### Scenario: 注册第一版个股 alpha 因子

- **WHEN** 系统定义第一版个股 alpha 因子
- **THEN** 每个因子 MUST 具有唯一 `factor_id`
- **THEN** 每个因子 MUST 声明中文说明、依赖数据、计算频率、可解释说明和标准化约定

#### Scenario: 缺少元数据的因子定义

- **WHEN** 某个因子缺少 `factor_id`、as-of 约束或标准化约定
- **THEN** 系统 SHALL NOT 将其视为正式 catalog 成员
- **THEN** 系统 MUST 返回缺失字段说明

### Requirement: 个股 alpha 因子目录不得直接耦合主策略行为

第一条 change 中的 `factor_catalog` MUST 只定义研究层正式因子，不得直接改写 `baseline_V10.1` 的默认选股、状态、预算或执行行为。

#### Scenario: 因子目录进入主路径

- **WHEN** 个股 alpha 因子目录进入正式主路径
- **THEN** 它 MUST 只承担研究定义与可观测合同
- **THEN** runtime SHALL NOT 因为 catalog 存在而自动改变主策略行为
