## ADDED Requirements

### Requirement: A0 V2 必须定义为核心槽位加成长卫星槽位
系统 MUST 提供 `cn-broad-based-etf-rotation-a0-core-satellite-v2` 研究能力，并将 A0 从“全池自由 Top2”改为“双槽位”结构。

其中：
- `core_slot` MUST 只从核心宽基候选中选择 1 个
- `growth_slot` MUST 只从成长位候选中选择 1 个
- 两个槽位的合并结果 MAY 同时持有 0 到 2 个 ETF

#### Scenario: 核心槽位与成长槽位独立选择
- **WHEN** A0 V2 在某个调仓日构建 ETF 组合
- **THEN** 系统 MUST 先在核心槽位候选中选择核心宽基标的
- **THEN** 系统 MUST 再在成长槽位候选中独立判断是否持有成长位

### Requirement: A0 V2 必须复用 A0 胜出版骨架
A0 V2 MUST 默认复用当前 A0 胜出版骨架：
- 月频调仓
- `MA200 + 12M>0` 绝对过滤
- `12M/6M/3M` 相对强弱
- `511010.SH` fallback
- `159915.SZ` 作为默认成长位

除槽位化构建与 proxy 替换外，系统 SHALL NOT 在同一轮中再引入新的主规则变量。

#### Scenario: A0 V2 默认控制组保持旧骨架不变
- **WHEN** 系统创建 A0 V2 的默认控制组
- **THEN** 其月频、绝对过滤、动量窗口和 fallback MUST 与 A0 胜出版保持一致

### Requirement: A0 V2 必须支持最小 proxy 替换 AB
A0 V2 MUST 支持以下最小 proxy 替换模式：
- `NONE`
- `CSI1000_PROXY_ONLY`
- `DIVIDEND_PROXY_ONLY`
- `FULL_STANDARD_SWAP`

其中：
- `CSI1000_PROXY_ONLY` MUST 表示 `512100.SH -> 159845.SZ`
- `DIVIDEND_PROXY_ONLY` MUST 表示 `512890.SH -> 510880.SH`
- `FULL_STANDARD_SWAP` MUST 同时执行上述两项替换

#### Scenario: 单点替换可被独立运行
- **WHEN** 用户运行 `CSI1000_PROXY_ONLY`
- **THEN** 系统 MUST 只替换中证1000代理，而保持红利代理不变

#### Scenario: 全替换仍需明确标记为实验模式
- **WHEN** 用户运行 `FULL_STANDARD_SWAP`
- **THEN** 系统 MUST 在产物中明确其为 A0 V2 的替换实验，而不是 A1 正式资产池
