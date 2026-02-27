## ADDED Requirements

### Requirement: ALL_A 模式解析
当 `universe_mode` 为 `ALL_A` 时，resolver SHALL 返回截至回测开始日期的全部活跃 A 股代码列表，使用已有的 `load_constituents_from_db()` 逻辑（pit_security_master + pams_ohlcv_daily）。

#### Scenario: ALL_A 返回全市场
- **WHEN** `universe_mode='ALL_A'`，`as_of='2023-01-01'`
- **THEN** resolver SHALL 返回截至 2023-01-01 在 pit_security_master 中上市且未退市、且有 OHLCV 数据的全部 CN_A 股票

### Requirement: HS300_ZZ500 模式解析
当 `universe_mode` 为 `HS300_ZZ500` 时，resolver SHALL 从 `pit_index_constituents` 表查询截至回测开始日期已纳入中证800的成分股。查询条件 SHALL 为 `start_date <= as_of AND (end_date IS NULL OR end_date > as_of)`，防止未来函数。

#### Scenario: HS300_ZZ500 按纳入日期过滤
- **WHEN** `universe_mode='HS300_ZZ500'`，`as_of='2020-01-01'`
- **THEN** 纳入日期晚于 2020-01-01 的成分股 SHALL NOT 出现在返回列表中

#### Scenario: HS300_ZZ500 表为空时降级
- **WHEN** `pit_index_constituents` 表为空或查询无结果
- **THEN** resolver SHALL 抛出 `UniverseLoadError`，前端显示"请先运行数据导入"提示

### Requirement: INDUSTRY 模式解析
当 `universe_mode` 为 `INDUSTRY` 时，resolver SHALL 接收 `industries` 参数（申万一级行业名称列表，如 `["银行", "食品饮料"]`），从 `pit_industry_history` 表查询截至回测开始日期属于所选行业的股票。查询条件 SHALL 为 `start_date <= as_of AND (end_date IS NULL OR end_date > as_of)`。

#### Scenario: 按行业筛选
- **WHEN** `universe_mode='INDUSTRY'`，`industries=['银行']`，`as_of='2023-01-01'`
- **THEN** resolver SHALL 返回截至 2023-01-01 行业分类为"银行"的全部股票

#### Scenario: 多行业合并
- **WHEN** `industries=['银行', '非银金融']`
- **THEN** resolver SHALL 返回两个行业的并集

#### Scenario: 行业表为空时降级
- **WHEN** `pit_industry_history` 表为空
- **THEN** resolver SHALL 抛出 `UniverseLoadError`，提示先运行数据导入

### Requirement: CUSTOM 模式解析
当 `universe_mode` 为 `CUSTOM` 时，resolver SHALL 直接使用用户提供的 `symbols` 列表，与现有行为一致。

#### Scenario: 用户自定义列表
- **WHEN** `universe_mode='CUSTOM'`，`symbols=['600519.SH', '000001.SZ']`
- **THEN** resolver SHALL 原样返回该列表（经过 normalize_stock_symbol 标准化）

### Requirement: resolver 返回元数据
resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 包含 `symbols_source`（模式名）、`raw_count`（原始数量）、`universe_mode`。该元数据 SHALL 写入 `run_meta.json` 供可观测性验证。

#### Scenario: run_meta 记录 universe 来源
- **WHEN** 回测使用 `INDUSTRY` 模式，选择"银行"行业，结果 42 只股票
- **THEN** `run_meta.json` 的 `universe` 字段 SHALL 包含 `{"mode": "INDUSTRY", "industries": ["银行"], "symbols_count": 42, "source": "pit_industry_history"}`

### Requirement: experiment_runner 集成
`experiment_runner.run_experiment()` SHALL 在加载配置后、执行回测前，调用 universe resolver 解析 symbols 列表，替代当前直接使用 `cfg_obj.universe.symbols` 的逻辑。

#### Scenario: 端到端集成
- **WHEN** 前端发送 `universe_mode='ALL_A'` 的回测请求
- **THEN** experiment_runner SHALL 调用 resolver 获取全 A 股列表，传入引擎执行回测
