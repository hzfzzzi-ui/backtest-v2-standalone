# cn-stock-raw-source-governance Specification

## Purpose
浠?2026-03-22 褰掓。鍙樻洿鎭㈠鐨勪富瑙勬牸銆?
## Requirements
### Requirement: `v2` 构建 MUST 先落地原始源再生成 canonical 主表
系统 MUST 为 `trade_cal, stock_basic, daily, adj_factor, daily_basic, suspend_d, stk_limit, moneyflow` 建立原始落地层，并 SHALL NOT 继续使用 direct-to-final 的方式直接写入 `pams_ohlcv_daily_v2`。

#### Scenario: 原始源先写 raw 表
- **WHEN** 系统执行任一 `v2` 回填或增量同步任务
- **THEN** 系统 MUST 先将对应源数据写入 `raw` 表，再执行 canonical build

#### Scenario: 原始表保留回放所需元信息
- **WHEN** 系统写入任一 `raw` 表
- **THEN** 每条原始记录 MUST 保留至少一个可追溯的 `source_run_id` 或等价批次标识
- **THEN** 系统 MUST 记录原始写入时间以支持重放和差异诊断

### Requirement: `v2` 原始源 MUST 明确主源与补源边界
系统 MUST 将 `Tushare` 视为 `v2` 数据库补全的主源，并将 `AkShare` 限制为少数字段的补源或审计源。系统 SHALL NOT 将 `AkShare` 当作 `daily_basic` 或 `moneyflow` 的全历史等价主源。

#### Scenario: `AkShare` 仅补 `turnover_rate`
- **WHEN** 构建主表需要补齐 `turnover_rate`
- **THEN** 系统 MAY 使用 `AkShare stock_zh_a_hist` 作为 `Tushare daily_basic` 的补源
- **THEN** 系统 SHALL NOT 以 `AkShare` 替代 `daily_basic` 的全字段主源地位

#### Scenario: `AkShare` 仅用于股本事件审计
- **WHEN** 系统需要校验或补算 `float_share`
- **THEN** 系统 MAY 使用 `AkShare stock_share_change_cninfo` 作为事件型审计源
- **THEN** 系统 SHALL NOT 将其视为现成日频面板源

### Requirement: `v2` 全历史回填 MUST 覆盖正式时间窗口
系统 MUST 支持 `2007-01-04` 到 `2026-03-20` 的全历史回填与重放，并将该窗口视为 `v2` 数据库补全的正式时间范围。系统 MUST 让 raw、canonical、moneyflow、AkShare fallback、full backfill 默认值与 runbook 正式命令共享同一 official window 终点定义。

#### Scenario: 全历史回填窗口固定
- **WHEN** 系统执行正式 `v2` 全量回填
- **THEN** 系统 MUST 覆盖 `2007-01-04` 到 `2026-03-20`

#### Scenario: 单日或分段回填与全量逻辑一致
- **WHEN** 系统执行单日、分段或补丁式回填
- **THEN** 系统 MUST 使用与全量回填相同的原始标准化和 canonical build 逻辑
- **THEN** 系统 SHALL NOT 为了快速补数据引入第二套写表逻辑

#### Scenario: 正式入口默认终点一致
- **WHEN** 用户运行正式 `v2` raw、main、moneyflow、audit 或 full backfill 入口且未显式指定截止日期
- **THEN** 系统 MUST 使用同一个 official window 终点
- **THEN** 系统 SHALL NOT 继续在不同入口保留彼此不一致的硬编码默认终点
