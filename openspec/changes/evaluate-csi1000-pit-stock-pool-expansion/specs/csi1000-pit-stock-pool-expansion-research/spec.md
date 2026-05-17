## ADDED Requirements

### Requirement: A2 必须只测试 CSI1000_new 当日市值门槛

系统 MUST 提供 research-only `A2_HS300_ZZ500_CSI1000_MCAP100` 对照实验，用于验证 A1 失败后新增 CSI1000 标的的市值段纪律。该实验 MUST 保持 `HS300_ZZ500_CSI1000 + PIT_DYNAMIC` 股票池、排序、入场、退出、仓位、成本和执行时点不变，只允许对当日属于 `000852.SH` 且不属于 `000906.SH` 的 `CSI1000_new` 标的应用当日流通市值门槛。系统 SHALL NOT 通过全窗口静态 symbol list 或事后幸存者名单表达该门槛。

#### Scenario: A2 只门控新增 CSI1000 低市值入选
- **WHEN** 运行 `A2_HS300_ZZ500_CSI1000_MCAP100`
- **THEN** `000906.SH` 原池标的必须沿用 B0/A1 的原有可交易门控
- **THEN** `CSI1000_new` 标的仅在当日 `circ_mv >= 100` 亿元时可进入买入候选
- **THEN** 已持仓标的的退出规则不得因该门槛被替换或放宽
- **THEN** 产物必须暴露该门槛配置和被门控的候选/交易影响，供 B0/A1/A2 同窗比较

### Requirement: 系统必须支持 CSI800 + CSI1000 的 PIT 联合股票池研究口径

系统 MUST 提供 `HS300_ZZ500_CSI1000` universe mode，用于表达 `HS300 + ZZ500 + CSI1000 PIT` 的研究股票池。该 mode MUST 从 `pit_index_constituents` 中 union `000906.SH` 与 `000852.SH` 的历史区间成员。系统 SHALL NOT 通过静态 `CUSTOM` symbol list 表达该研究池。

#### Scenario: 解析联合 PIT 快照

- **WHEN** resolver 以 `HS300_ZZ500_CSI1000` 和某个 `as_of` 日期解析股票池
- **THEN** 返回 symbol MUST 等于 `000906.SH` 与 `000852.SH` 在该日期有效成分的去重 union
- **THEN** meta MUST 暴露 `index_codes=["000906.SH","000852.SH"]`
- **THEN** meta MUST 标注 `symbols_source="pit_index_constituents"`

### Requirement: 动态 membership 构建必须保留两个指数的历史区间并审计 CSI1000 子集

当 `membership_mode=PIT_DYNAMIC` 且 `universe_mode=HS300_ZZ500_CSI1000` 时，系统 MUST 分别读取 `000906.SH` 与 `000852.SH` 的 membership history，合并后作为动态成员门控。系统 MUST 对 `000852.SH` 子集单独执行 refresh sidecar 审计，并在 static fallback 时阻断，除非显式开启低保真研究。

#### Scenario: 联合动态 membership 保留 index_code

- **WHEN** 构建 `HS300_ZZ500_CSI1000 + PIT_DYNAMIC` 数据包
- **THEN** membership history MUST 包含 `000906.SH` 与 `000852.SH` 两类 `index_code`
- **THEN** union symbol count MUST 来自两个指数历史成员去重
- **THEN** data bundle summary MUST 标明 `historical_membership_dynamic=true`

#### Scenario: CSI1000 static fallback 被阻断

- **WHEN** `000852.SH` 子集被审计为 `static_fallback`
- **AND** `universe.allow_low_fidelity_history` 未开启
- **THEN** 系统 MUST 阻断该数据包构建
- **THEN** 错误信息 MUST 包含 `csi1000`、`static_fallback` 和审计原因

### Requirement: 股票池扩展研究必须先 stock-only，后 combo

系统 MUST 提供 research-only stock-only study，先比较当前 `HS300_ZZ500 + PIT_DYNAMIC` 与 `HS300_ZZ500_CSI1000 + PIT_DYNAMIC`。该 study MUST 不修改 alpha、ranking、entry、exit、risk budget、ETF sleeve 或 combo allocator。

#### Scenario: 生成 stock-only A/B 执行计划

- **WHEN** 用户对本 study 执行 dry-run
- **THEN** 执行计划 MUST 包含 `B0_HS300_ZZ500` 与 `A1_HS300_ZZ500_CSI1000`
- **THEN** 两个 variant MUST 只在 `universe_mode` 上不同
- **THEN** study MUST 标注 research-only

### Requirement: 本轮研究必须输出静态审计证据后再解释收益

系统 MUST 在解释任何回测收益前先输出静态审计证据，包括窗口 symbol 数、新增与重叠、OHLCV 覆盖、ST/停牌/退市过滤风险、行业覆盖、CSI1000 provider floor、数据规模和预估运行时影响。

#### Scenario: 静态审计识别 CSI1000 覆盖下限

- **WHEN** 审计窗口早于 CSI1000 provider floor
- **THEN** 审计输出 MUST 明确 `csi1000_provider_floor_date`
- **THEN** 结论 MUST 标注早于该日期的 CSI1000 成员证据不完整
- **THEN** 系统 SHALL NOT 将该窗口表述为完整正式 CSI1000 PIT 覆盖
### Requirement: CSI1000 扩池失败后必须输出负贡献归因

当 `A1_HS300_ZZ500_CSI1000` 在主窗口显著弱于 `B0_HS300_ZZ500` 时，系统 MUST 输出 research-only 负贡献归因，至少覆盖新增 CSI1000 标的在行业、流动性、市值段、排序分位、交易成本和退出规则上的贡献。该归因 SHALL NOT 修改 baseline、交易口径、信号口径或 universe 定义。

#### Scenario: 主窗口 A1 失败后执行归因

- **WHEN** `A1_HS300_ZZ500_CSI1000` 主窗口同窗比较弱于 B0
- **THEN** 系统 MUST 生成按 PIT membership 分类的贡献表，区分 `csi1000_new`、`csi800_only`、`overlap` 和 `unclassified`
- **THEN** 系统 MUST 生成行业、流动性、市值段、排序分位和退出规则维度的机器可读输出
- **THEN** 归因报告 MUST 明确说明结论是直接交易贡献、候选排序压力还是退出阶段拖累
