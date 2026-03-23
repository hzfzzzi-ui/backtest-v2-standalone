# universe-resolver Specification

## Purpose
Backend universe resolver that supports 4 modes (ALL_A, HS300_ZZ500, INDUSTRY, CUSTOM) for determining the stock universe used in backtests, replacing the previous single-mode symbol list approach.
## Requirements
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
resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 除了原有 `symbols_source`、`raw_count` 和 `universe_mode` 外，在 `PIT_DYNAMIC` 指数股票池场景下还 MUST 暴露足够的 lineage 质量字段，用于区分正式单源历史链与低保真 fallback。

resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 除了原有 `symbols_source`、`raw_count` 和 `universe_mode` 外，在 `PIT_DYNAMIC` 指数股票池场景下还 MUST 暴露足够的 lineage 质量字段，用于区分正式单源历史链与低保真 fallback。

resolver SHALL 返回 `(symbols, meta)` 元组，其中 `meta` 除了原有 `symbols_source`、`raw_count` 和 `universe_mode` 外，在 `PIT_DYNAMIC` 指数股票池场景下还 MUST 暴露足够的 lineage 质量字段，用于区分正式单源历史链与低保真 fallback。

#### Scenario: HS300_ZZ500 暴露正式 lineage 元数据
- **WHEN** 回测使用 `universe_mode='HS300_ZZ500'` 且 membership mode 为 `PIT_DYNAMIC`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `index_code='000906.SH'`
- **THEN** `meta` 或其后续落盘的等价元信息 MUST 包含 `membership_source`、`membership_data_quality`、`membership_history_rows` 和 `distinct_start_dates`

#### Scenario: 正式入口不得继续引用月度链为 formal lineage
- **WHEN** 系统对外暴露 `HS300_ZZ500` 的正式导入资产或 lineage 说明
- **THEN** 正式入口 MUST 指向新的 `Tushare` 历史链
- **THEN** 旧月度脚本只能作为 fallback/approximate 说明存在，MUST NOT 再被标注为 formal lineage### Requirement: experiment_runner 集成
`experiment_runner.run_experiment()` SHALL 在加载配置后、执行回测前，调用 universe resolver 解析 symbols 列表，替代当前直接使用 `cfg_obj.universe.symbols` 的逻辑。

#### Scenario: 端到端集成
- **WHEN** 前端发送 `universe_mode='ALL_A'` 的回测请求
- **THEN** experiment_runner SHALL 调用 resolver 获取全 A 股列表，传入引擎执行回测

#### Scenario: 正式入口改为正式历史链物化
- **WHEN** 系统对外暴露 `HS300_ZZ500` 的正式导入资产或 lineage 说明
- **THEN** 正式入口 MUST 指向“长历史 seed/正式链物化 -> replace import”
- **THEN** `Tushare trade_date` 抓取脚本只可作为正式链 tail update 来源或 fallback 说明，MUST NOT 再被描述为单独可用的全历史 formal lineage

### Requirement: Universe resolver 必须先按 asset family 分发
系统 MUST 让 universe resolver 入口先消费 canonical `asset_profile`，再把解析流程分发到对应的 asset-family resolver。当前 A 股 resolver SHALL 只是其中一个 adapter，且 resolver 返回的元数据 MUST 显式暴露 `asset_scope`、`asset_profile_id` 与 `asset_family`。

#### Scenario: 运行 A 股 universe 解析
- **WHEN** runtime compile 传入当前 canonical A 股 asset profile
- **THEN** resolver MUST 路由到 A 股 adapter
- **THEN** 解析结果 MUST 与当前 `V10.1` universe 语义等价

#### Scenario: A 股 resolver 回填资产元数据
- **WHEN** `asset_scope='cn_a_equity'` 进入 resolver
- **THEN** 返回的 `meta` MUST 暴露 `asset_scope='cn_a_equity'`
- **THEN** 返回的 `meta` MUST 暴露 `asset_profile_id` 和 `asset_family`

#### Scenario: 运行未支持资产的 universe 解析
- **WHEN** runtime compile 传入尚未实现的 asset profile
- **THEN** resolver MUST 返回显式 unsupported error
- **THEN** 系统 SHALL NOT 继续复用 A 股 resolver

#### Scenario: 未支持资产的错误必须可审计
- **WHEN** `asset_scope='us_equity'` 进入当前 resolver
- **THEN** 错误元信息 MUST 暴露 `asset_scope='us_equity'`
- **THEN** 错误元信息 MUST 暴露当前 `universe_mode`

### Requirement: A 股 resolver 规则必须作为 asset-specific adapter 保留
系统 MUST 将 `ALL_A`、`HS300_ZZ500`、`INDUSTRY`、`CUSTOM` 等现有 A 股 universe 解析规则保留在 A 股 adapter 内，而 SHALL NOT 把它们继续定义成默认全局 universe 主语义。

#### Scenario: A 股行业模式解析
- **WHEN** A 股 profile 使用 `INDUSTRY` 模式
- **THEN** 系统 MUST 继续使用现有 A 股行业历史数据规则
- **THEN** 这些规则 SHALL 仅在 A 股 adapter 内生效

### Requirement: Universe resolver 必须正式支持 CSI1000 历史成分口径
系统 MUST 将 `CSI1000` 视为正式支持的指数股票池模式，并在 `PIT_DYNAMIC` 口径下使用 `pit_index_constituents` 中 `index_code='000852.SH'` 的历史成分记录，而不是把它视作临时脚本输出。

#### Scenario: 解析中证1000历史成分
- **WHEN** `universe_mode='CSI1000'` 且 `membership_mode='PIT_DYNAMIC'`
- **THEN** resolver 或其上游数据加载链路 MUST 从 `pit_index_constituents` 的 `000852.SH` 历史记录生成成分并集和 membership history

#### Scenario: 缺失历史成分时报错
- **WHEN** `CSI1000` 的 `PIT_DYNAMIC` 请求缺少有效历史成分记录
- **THEN** 系统 MUST 返回可审计的错误或告警
- **THEN** 系统 MUST 不得静默回退到最新静态成分

### Requirement: CSI1000 resolver 元信息必须暴露 lineage 与质量字段
系统 MUST 为 `CSI1000` 的 resolver/data bundle 输出足够的 lineage 和质量元信息，以便研究者判断该 universe 是否具备 PIT 可信度。

#### Scenario: 输出中证1000 lineage 元信息
- **WHEN** 回测使用 `CSI1000` 股票池
- **THEN** `run_meta.json` 或等价元信息 MUST 包含 `index_code`、`membership_mode`、`membership_history_rows`、`union_symbol_count`、`membership_source` 和 `membership_data_quality`

#### Scenario: 标记动态成分门控模式
- **WHEN** `CSI1000` 使用历史成分门控
- **THEN** 元信息 MUST 显式标记 `historical_membership_dynamic=true`
- **THEN** 元信息 MUST 显式标记当前过滤模式为基于动态成分的门控，而不是静态预过滤

### Requirement: Universe filters MUST 支持可选科创板排除
系统 MUST 在共享 `universe.filters` 链路中支持布尔字段 `exclude_star_market`。当该字段为 `true` 时，resolver SHALL 在候选集合与股票代码集合两个层面排除科创板标的；当字段缺省或为 `false` 时，系统 SHALL 保持现有股票池行为不变。

#### Scenario: 默认关闭不改变现有股票池
- **WHEN** 运行配置未提供 `universe.filters.exclude_star_market`
- **THEN** resolver SHALL 不额外排除任何科创板标的
- **THEN** 结果股票池口径 SHALL 与改动前保持一致

#### Scenario: 显式开启后排除科创板
- **WHEN** `universe.filters.exclude_star_market=true`
- **THEN** resolver SHALL 排除标准化后属于 `688xxx.SH` 或 `689xxx.SH` 的 A 股标的
- **THEN** 非科创板 A 股标的 SHALL 保留

### Requirement: 科创板过滤结果 MUST 写入现有 universe 元数据
当科创板过滤启用时，系统 MUST 将过滤配置与排除计数写入现有 universe 元数据，确保验证接口、bundle 构建与真实执行可以审计该过滤是否生效。

#### Scenario: 记录过滤配置与排除数量
- **WHEN** `exclude_star_market=true` 且股票池中存在科创板标的
- **THEN** universe 元数据 SHALL 在 `filters_config` 中记录 `exclude_star_market=true`
- **THEN** universe 元数据 SHALL 在 `excluded_counts` 中记录 `EXCLUDE_STAR_MARKET` 的排除数量

### Requirement: Dynamic universe 路径 MUST 复用同一科创板过滤语义
系统 MUST 让 dynamic universe 解析路径与静态候选过滤路径复用同一套科创板识别和排除语义，避免验证结果、bundle 构建和运行期消费出现口径分叉。

#### Scenario: Dynamic ALL_A 路径启用科创板过滤
- **WHEN** `membership_mode` 为 dynamic 路径且 `exclude_star_market=true`
- **THEN** 下游消费的 symbol 列表 SHALL 在进入可交易集合前排除科创板标的
- **THEN** 实际运行期股票池 SHALL 与验证接口返回的过滤结果一致

### Requirement: Universe resolver 必须支持 `cn_etf` 的受控 `CUSTOM` 解析
当 `asset_scope='cn_etf'` 且 `universe_mode='CUSTOM'` 时，resolver MUST 只从正式 ETF 目录中解析 ETF 代码，并返回 ETF 资产元数据。resolver SHALL NOT 复用 A 股个股的股票池查询、股票行业筛选或指数成分股逻辑。

#### Scenario: 解析单只 ETF
- **WHEN** `asset_scope='cn_etf'`、`universe_mode='CUSTOM'` 且 `symbols=['512100.SH']`
- **THEN** resolver MUST 返回标准化后的 `512100.SH`
- **THEN** 返回的 `meta` MUST 包含 `asset_scope='cn_etf'` 与 ETF 目录来源标识

#### Scenario: 拒绝未纳入目录的 ETF
- **WHEN** `asset_scope='cn_etf'`、`universe_mode='CUSTOM'` 且 `symbols` 包含未纳入首波目录的代码
- **THEN** resolver MUST 返回显式错误
- **THEN** 系统 SHALL NOT 静默保留未知 symbol 或回退到股票 resolver

### Requirement: Universe resolver 必须支持 ETF 预设组展开
系统 MUST 支持把 ETF 研究 preset 展开为受控 symbol 列表并进入 `cn_etf` resolver。预设组至少包括 `cn_etf_first_wave_core` 和 `cn_etf_first_wave_all`，且展开结果 MUST 与正式 ETF 目录一致。

#### Scenario: 核心批次 ETF 预设组展开
- **WHEN** 运行配置声明 `asset_scope='cn_etf'` 且 preset 为 `cn_etf_first_wave_core`
- **THEN** resolver 或其上游编译链路 MUST 展开出核心批次 6 只 ETF
- **THEN** resolver 返回的 `meta` MUST 暴露 `preset_id='cn_etf_first_wave_core'`

#### Scenario: 全批次 ETF 预设组展开
- **WHEN** 运行配置声明 `asset_scope='cn_etf'` 且 preset 为 `cn_etf_first_wave_all`
- **THEN** resolver 或其上游编译链路 MUST 展开出首波全部 9 只 ETF
- **THEN** 展开结果 MUST 不包含目录外 symbol


