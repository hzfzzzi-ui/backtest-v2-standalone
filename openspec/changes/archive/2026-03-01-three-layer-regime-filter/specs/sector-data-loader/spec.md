## ADDED Requirements

### Requirement: 行业指数 OHLCV 加载

系统 SHALL 提供方法从 `pit_index_daily` 表加载申万 L1 行业指数日线数据（index_code LIKE '801%.SI'）。

返回格式：按 index_code 组织的 DataFrame（columns: trade_date, open, high, low, close, volume, turnover），或等效的 dict[str, pd.DataFrame] 结构。

#### Scenario: 加载指定日期范围
- **WHEN** 调用 `load_sector_index_data(start_date, end_date)`
- **THEN** 返回所有 801xxx.SI 行业指数在 [start_date, end_date] 范围内的 OHLCV 日线数据

#### Scenario: 行业指数不存在
- **WHEN** pit_index_daily 中不存在任何 801xxx.SI 数据
- **THEN** 返回空结构，不抛出异常

---

### Requirement: 股票-行业映射加载

系统 SHALL 提供方法从 `pit_industry_history` 表加载 PIT-safe 的股票→行业 L1 映射。

给定一组 symbols 和一组 trading_days，返回每只股票在每个交易日所属的 `industry_l1` 名称。

#### Scenario: PIT-safe 映射
- **WHEN** 股票 A 在 2020-01-01 前属于"商贸零售"，2020-01-01 后属于"银行"
- **THEN** 查询 2019-12-31 返回"商贸零售"，查询 2020-01-02 返回"银行"

#### Scenario: 无行业记录
- **WHEN** 某股票在 pit_industry_history 中无记录
- **THEN** 该股票的行业映射为 None，Sector 层门控默认 1.0

---

### Requirement: 行业名→行业指数代码映射

系统 SHALL 提供 `industry_l1` 名称（如 "银行"）到 行业指数代码（如 "801780.SI"）的映射。

映射方式：从 `sw_index_first_info()` 动态获取，或使用内置常量表。31 个申万 L1 行业 MUST 全覆盖。

#### Scenario: 名称到代码查询
- **WHEN** 查询行业 "银行" 的指数代码
- **THEN** 返回 "801780.SI"

#### Scenario: 未知行业名
- **WHEN** 查询不在映射中的行业名
- **THEN** 返回 None，该行业的 Sector 层门控默认 1.0

---

### Requirement: 行业指数矩阵构建

系统 SHALL 提供方法将行业指数 OHLCV 数据构建为矩阵格式，供 RegimeFilter 向量化计算。

输出矩阵形状为 T × S（T = 交易日数，S = 行业数），按 trading_days 对齐。行业无数据的日期填充 NaN。

#### Scenario: 矩阵对齐
- **WHEN** trading_days 为 2016-03-01 ~ 2026-02-13，801960.SI 仅有 2021-12-13 起的数据
- **THEN** 801960.SI 对应列在 2021-12-13 前填充 NaN

#### Scenario: 矩阵列顺序稳定
- **WHEN** 多次调用矩阵构建
- **THEN** 行业列顺序保持一致（按 index_code 字母序排列）

---

### Requirement: 数据缓存

行业指数数据和行业映射在单次回测中 MUST 只从数据库加载一次。后续访问从内存缓存获取。

#### Scenario: 重复调用不产生 DB 查询
- **WHEN** 同一回测中第二次请求行业指数数据
- **THEN** 直接返回缓存数据，不执行 SQL 查询
