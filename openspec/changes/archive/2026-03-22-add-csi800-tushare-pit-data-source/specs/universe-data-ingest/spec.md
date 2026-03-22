## MODIFIED Requirements

### Requirement: 指数成分导入
系统 SHALL 提供 `CSI800` 指数成分导入链，并区分正式 `Tushare` 历史链与低保真 fallback。正式链 MUST 基于 `000906.SH` 的历史变化记录导入 `pit_index_constituents`，不得继续把月度近似 patch 默认当作正式研究入口。

#### Scenario: 正式 CSI800 历史导入
- **WHEN** 执行正式 `CSI800` PIT refresh 或导入命令
- **THEN** 系统 MUST 导入由正式 `Tushare` 历史链生成的 `changes.csv`
- **THEN** 导入后的 `pit_index_constituents` 中 `index_code='000906.SH'` 记录 MUST 使用非 `monthly` 的正式 source label

#### Scenario: 低保真 fallback 保留但不得冒充正式链
- **WHEN** 用户显式运行旧月度脚本或其他低保真 fallback
- **THEN** 系统 MAY 允许生成近似 changes 文件
- **THEN** 这些记录的 source label MUST 明确包含 `monthly`、`approximate`、`static` 或等价低保真语义

## ADDED Requirements

### Requirement: CSI800 正式导入必须支持单源全量替换
系统 MUST 为 `CSI800` 正式导入提供显式的全量替换路径，只替换 `pit_index_constituents` 中 `index_code='000906.SH'` 的记录，避免 patch merge 形成 `mixed` source。

#### Scenario: 正式导入全量替换 000906.SH 分区
- **WHEN** 正式 `CSI800` 导入以全量替换模式执行
- **THEN** 系统 MUST 删除并重写 `index_code='000906.SH'` 的历史记录
- **THEN** 系统 MUST NOT 修改其他指数代码的历史数据

#### Scenario: 兼容 patch merge 仅在显式模式下使用
- **WHEN** 用户未选择正式全量替换，而是显式执行兼容 patch merge
- **THEN** 系统 MAY 继续使用旧 merge 口径
- **THEN** 系统 MUST 将该模式与正式导入路径清晰区分

### Requirement: CSI800 导入必须输出结构化摘要
系统 MUST 在 `CSI800` 导入前后输出结构化摘要，便于审计 source、distinct start dates 和替换结果。

#### Scenario: 导入摘要包含前后对比
- **WHEN** `CSI800` 导入完成
- **THEN** 系统 MUST 输出至少包含 `rows`、`distinct_symbols`、`distinct_start_dates`、`open_rows`、`closed_rows` 和 `membership_source` 的导入摘要
- **THEN** 正式 refresh MUST 将该摘要写入可复核的 `summary.json`
