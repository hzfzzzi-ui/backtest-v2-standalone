# universe-data-ingest Specification

## Purpose
Data import scripts for ingesting industry classification history and index constituent data from AKShare into the backtest database, providing the foundational data required by universe resolver modes (INDUSTRY, HS300_ZZ500).
## Requirements
### Requirement: 行业分类历史导入
系统 SHALL 提供导入脚本，从 AKShare `stock_industry_clf_hist_sw()` 拉取全量申万行业分类历史数据，写入 `pit_industry_history` 表。数据 SHALL 包含 `ts_code`、`start_date`、`end_date`（从下一条记录推算）、`standard`（固定 `SW2021`）、`industry_l1`（通过 code 前2位映射到31个申万一级行业名称）、`industry_l2`（industry_code 完整值）。

#### Scenario: 全量导入行业数据
- **WHEN** 运行导入脚本 `python -m backend.core.universe.ingest_universe --industry`
- **THEN** `pit_industry_history` 表 SHALL 写入约 12,000+ 条记录，覆盖 5,800+ 只股票，start_date 最早回溯到 2010-01-01

#### Scenario: end_date 推算防未来函数
- **WHEN** 同一只股票有多条行业变更记录（如平安银行 440101→480101→480301）
- **THEN** 前一条记录的 `end_date` SHALL 设为下一条记录的 `start_date`，最后一条记录的 `end_date` SHALL 为 NULL（表示当前仍有效）

#### Scenario: 幂等性
- **WHEN** 导入脚本重复执行
- **THEN** SHALL 先清空再写入（TRUNCATE + INSERT），保证数据一致性

### Requirement: 指数成分导入
系统 SHALL 提供 `CSI800` 指数成分导入链，并区分正式 `Tushare` 历史链与低保真 fallback。正式链 MUST 基于 `000906.SH` 的历史变化记录导入 `pit_index_constituents`，不得继续把月度近似 patch 默认当作正式研究入口。

系统 SHALL 提供 `CSI800` 指数成分导入链，并区分正式 `Tushare` 历史链与低保真 fallback。正式链 MUST 基于 `000906.SH` 的历史变化记录导入 `pit_index_constituents`，不得继续把月度近似 patch 默认当作正式研究入口。

#### Scenario: 正式 CSI800 历史导入
- **WHEN** 执行正式 `CSI800` PIT refresh 或导入命令
- **THEN** 系统 MUST 导入由正式 `Tushare` 历史链生成的 `changes.csv`
- **THEN** 导入后的 `pit_index_constituents` 中 `index_code='000906.SH'` 记录 MUST 使用非 `monthly` 的正式 source label

#### Scenario: 低保真 fallback 保留但不得冒充正式链
- **WHEN** 用户显式运行旧月度脚本或其他低保真 fallback
- **THEN** 系统 MAY 允许生成近似 changes 文件
- **THEN** 这些记录的 source label MUST 明确包含 `monthly`、`approximate`、`static` 或等价低保真语义### Requirement: 新建 pit_index_constituents 表
导入脚本 SHALL 在首次运行时自动创建 `pit_index_constituents` 表（如不存在），包含字段：`index_code VARCHAR`、`symbol VARCHAR`、`start_date DATE`、`end_date DATE`、`source VARCHAR`、`created_at TIMESTAMPTZ`。

#### Scenario: 表自动创建
- **WHEN** `pit_index_constituents` 表不存在时运行导入脚本
- **THEN** 脚本 SHALL 自动执行 CREATE TABLE IF NOT EXISTS

### Requirement: 同步更新 pit_security_master.industry
导入脚本 SHALL 用每只股票最新的行业分类更新 `pit_security_master.industry` 字段（当前全部为 NULL）。

#### Scenario: industry 字段回填
- **WHEN** 导入行业数据完成
- **THEN** `pit_security_master` 中有行业记录的股票的 `industry` 字段 SHALL 被更新为其最新的申万一级行业名称（如"银行"、"食品饮料"）

### Requirement: CSI800 正式 refresh 必须阻止短历史误覆盖
系统 MUST 在 `CSI800` 正式 refresh 的导入阶段校验历史覆盖。若待导入正式链不能覆盖所需起点，且用户未提供长历史 seed 物化正式链，命令 MUST 在导入前失败并保持数据库不变。

系统 MUST 在 `CSI800` 正式 refresh 的导入阶段校验历史覆盖。若待导入正式链不能覆盖所需起点，且用户未提供长历史 seed 物化正式链，命令 MUST 在导入前失败并保持数据库不变。

#### Scenario: 裸 Tushare 抓取结果缺失 required_start
- **WHEN** 正式 refresh 只拿到从晚近日期开始的 `000906.SH` 历史，不能覆盖 `required_start`
- **THEN** 系统 MUST 跳过 `--replace-existing` 导入
- **THEN** 系统 MUST 输出结构化失败摘要，说明缺失起点和建议补充的 seed 路径

#### Scenario: 提供长历史 seed 后允许正式全量替换
- **WHEN** 正式 refresh 提供覆盖 `required_start` 的 seed CSV，并成功物化最终正式链
- **THEN** 系统 MUST 对 `pit_index_constituents(index_code='000906.SH')` 执行全量替换
- **THEN** 系统 MUST 输出 fetch/materialize/import 三段 summary 供人工复核

#### Scenario: 正式 CSI800 历史导入
- **WHEN** 执行正式 `CSI800` PIT refresh 或导入命令
- **THEN** 系统 MUST 导入由正式历史链物化步骤生成的 `changes.csv`
- **THEN** 导入后的 `pit_index_constituents` 中 `index_code='000906.SH'` 记录 MUST 使用单一 formal source label

#### Scenario: 低保真 fallback 保留但不得冒充正式链
- **WHEN** 用户显式运行旧月度脚本或其他低保真 fallback
- **THEN** 系统 MAY 允许生成近似 changes 文件
- **THEN** 这些记录的 source label MUST 明确包含 `monthly`、`approximate`、`static` 或等价低保真语义### Requirement: CSI800 正式导入必须支持单源全量替换
系统 MUST 为 `CSI800` 正式导入提供显式的全量替换路径，只替换 `pit_index_constituents` 中 `index_code='000906.SH'` 的记录，避免 patch merge 形成 `mixed` source。

系统 MUST 为 `CSI800` 正式导入提供显式的全量替换路径，只替换 `pit_index_constituents` 中 `index_code='000906.SH'` 的记录，避免 patch merge 形成 `mixed` source。

#### Scenario: 正式导入全量替换 000906.SH 分区
- **WHEN** 正式 `CSI800` 导入以全量替换模式执行
- **THEN** 系统 MUST 删除并重写 `index_code='000906.SH'` 的历史记录
- **THEN** 系统 MUST NOT 修改其他指数代码的历史数据

#### Scenario: 兼容 patch merge 仅在显式模式下使用
- **WHEN** 用户未选择正式全量替换，而是显式执行兼容 patch merge
- **THEN** 系统 MAY 继续使用旧 merge 口径
- **THEN** 系统 MUST 将该模式与正式导入路径清晰区分### Requirement: CSI800 导入必须输出结构化摘要
系统 MUST 在 `CSI800` 导入前后输出结构化摘要，便于审计 source、distinct start dates 和替换结果。

#### Scenario: 导入摘要包含前后对比
- **WHEN** `CSI800` 导入完成
- **THEN** 系统 MUST 输出至少包含 `rows`、`distinct_symbols`、`distinct_start_dates`、`open_rows`、`closed_rows` 和 `membership_source` 的导入摘要
- **THEN** 正式 refresh MUST 将该摘要写入可复核的 `summary.json`

### Requirement: CSI1000 导入链必须同时重建区间主表与 refresh 侧表
系统 MUST 在 `CSI1000` PIT 导入时同时重建 `pit_index_constituents(index_code='000852.SH')` 与 refresh 侧表，而 SHALL NOT 只导入 `changes.csv` 后丢弃 refresh 级 snapshots。

#### Scenario: Tushare refresh 导入
- **WHEN** 执行 `CSI1000` 的 Tushare PIT refresh 导入
- **THEN** 系统 MUST 同时消费 `changes.csv` 与 `snapshots.csv`
- **THEN** 导入事务 MUST 同时替换主区间表与 refresh 侧表的 `000852.SH` 分区

#### Scenario: 手工 official manifest 导入
- **WHEN** 执行 `CSI1000` 的 manual manifest 导入
- **THEN** 系统 MUST 同时生成并导入主区间 changes 与 refresh snapshots
- **THEN** refresh 侧表 MUST 保留 `source_url` 或等价 lineage 元信息

### Requirement: CSI1000 Tushare 导入必须显式记录实际快照交易日
系统 MUST 把 `Tushare index_weight` 实际命中的 `trade_date` 作为结构化字段保存到 `CSI1000` snapshots 和 refresh 侧表，而 SHALL NOT 继续仅把该值拼接进 `source_note`。

#### Scenario: Tushare 快照命中晚于 effective_date 的交易日
- **WHEN** 系统用 `lookahead` 在 `effective_date` 之后命中第一天可用的 `trade_date`
- **THEN** snapshots 输出 MUST 显式记录该 `snapshot_trade_date`
- **THEN** refresh 侧表 MUST 保留同一字段，供后续 SQL 与审计查询

### Requirement: CSI1000 Tushare 导入必须显式暴露覆盖下限
系统 MUST 在 `CSI1000` Tushare 导入摘要中显式暴露 provider 的最早快照覆盖日，并对早于该日期的目标窗口给出 uncovered 结论，而 SHALL NOT 把缺口伪装成 formal PIT 历史。

#### Scenario: 请求窗口早于 Tushare 最早覆盖日
- **WHEN** 用户目标窗口早于当前 `Tushare index_weight(000852.SH)` 的最早可用快照日期
- **THEN** 导入摘要 MUST 显式输出 `provider_floor_date` 或等价字段
- **THEN** 系统 MUST 将该窗口标记为 uncovered/approximate，而不是 formal

#### Scenario: 2012-2015 无源窗口不得被伪补齐
- **WHEN** `Tushare` 对 `2012-01-01 ~ 2015-07-30` 无可用 `CSI1000` 快照
- **THEN** 系统 MUST 保持该区间为无覆盖真相
- **THEN** 系统 SHALL NOT 用首个可用快照前向填充或静态 fallback 伪造正式 PIT

### Requirement: CSI1000 正式 PIT 数据导入必须以调样日历驱动
系统 MUST 为 `CSI1000` 提供正式的 PIT 数据导入链路，使用显式调样日历驱动快照抓取和变更重建，而不是默认按月采样或直接复用最新静态成分。

#### Scenario: 按调样日历生成快照
- **WHEN** 执行 `CSI1000` 正式 PIT 抓取脚本
- **THEN** 系统 MUST 按调样日历中的每个 `effective_date` 抓取对应成分快照
- **THEN** 系统 MUST 生成可复核的 snapshots 文件和 changes 文件

#### Scenario: 从相邻快照重建变更
- **WHEN** 系统拿到相邻两个 `CSI1000` 快照
- **THEN** 系统 MUST 通过 diff 重建 `in_date` 和 `out_date`
- **THEN** 最终 changes 文件 MUST 可直接导入 `pit_index_constituents` 的 `000852.SH` 分区

### Requirement: CSI1000 正式数据源必须标记来源与保真度
系统 MUST 在 `CSI1000` 导入链路中区分正式历史源、近似历史源和静态 fallback，并把来源标签写入导入结果。

#### Scenario: Tushare 正式来源标签
- **WHEN** `CSI1000` 快照由正式历史接口抓取
- **THEN** 导入记录 MUST 带有明确的 `source` 标签，例如 `tushare_csi1000_rebalance`

#### Scenario: 静态 fallback 来源标签
- **WHEN** 系统使用最新静态成分作为应急数据
- **THEN** 导入记录 MUST 带有 `static` 或等价的低保真来源标签
- **THEN** 系统 MUST NOT 将该结果默认为正式 PIT 历史

### Requirement: CSI1000 导入必须输出质量统计
系统 MUST 在导入或导入前检查阶段输出 `CSI1000` 成分历史的关键统计，便于审计和回滚。

#### Scenario: 输出导入统计
- **WHEN** `CSI1000` changes 文件被生成或导入完成
- **THEN** 系统 MUST 输出至少包含 `rows`、`distinct_symbols`、`distinct_start_dates`、`open_rows`、`min_start_date` 和 `max_start_date` 的统计摘要

#### Scenario: 导入只影响 000852.SH 分区
- **WHEN** 导入 `CSI1000` changes 文件
- **THEN** 系统 MUST 只替换 `pit_index_constituents` 中 `index_code='000852.SH'` 的记录
- **THEN** 系统 MUST NOT 修改其他指数代码的成分数据

### Requirement: CSI800 导入必须输出结构化摘要
系统 MUST 在 `CSI800` 导入前后输出结构化摘要，便于审计 source、distinct start dates 和替换结果。

#### Scenario: 导入摘要包含前后对比
- **WHEN** `CSI800` 导入完成
- **THEN** 系统 MUST 输出至少包含 `rows`、`distinct_symbols`、`distinct_start_dates`、`open_rows`、`closed_rows` 和 `membership_source` 的导入摘要
- **THEN** 正式 refresh MUST 将该摘要写入可复核的 `summary.json`
