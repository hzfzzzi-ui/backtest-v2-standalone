## ADDED Requirements

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
系统 SHALL 提供导入脚本，从 AKShare `index_stock_cons(symbol='000906')` 拉取中证800（沪深300+中证500合集）当前成分数据，写入新建的 `pit_index_constituents` 表。

#### Scenario: 全量导入指数成分
- **WHEN** 运行导入脚本 `python -m backend.core.universe.ingest_universe --index`
- **THEN** `pit_index_constituents` 表 SHALL 写入约 800 条记录，每条包含 `index_code`（'000906.SH'）、`symbol`（内部格式如 sz000001）、`start_date`（纳入日期）、`end_date`（NULL，因无移出数据）、`source`

#### Scenario: 纳入日期保真
- **WHEN** AKShare 返回某成分的纳入日期为 2020-06-15
- **THEN** 该记录的 `start_date` SHALL 为 2020-06-15，回测日期早于此日期时该股票 SHALL NOT 出现在指数 universe 中

### Requirement: 新建 pit_index_constituents 表
导入脚本 SHALL 在首次运行时自动创建 `pit_index_constituents` 表（如不存在），包含字段：`index_code VARCHAR`、`symbol VARCHAR`、`start_date DATE`、`end_date DATE`、`source VARCHAR`、`created_at TIMESTAMPTZ`。

#### Scenario: 表自动创建
- **WHEN** `pit_index_constituents` 表不存在时运行导入脚本
- **THEN** 脚本 SHALL 自动执行 CREATE TABLE IF NOT EXISTS

### Requirement: 同步更新 pit_security_master.industry
导入脚本 SHALL 用每只股票最新的行业分类更新 `pit_security_master.industry` 字段（当前全部为 NULL）。

#### Scenario: industry 字段回填
- **WHEN** 导入行业数据完成
- **THEN** `pit_security_master` 中有行业记录的股票的 `industry` 字段 SHALL 被更新为其最新的申万一级行业名称（如"银行"、"食品饮料"）
