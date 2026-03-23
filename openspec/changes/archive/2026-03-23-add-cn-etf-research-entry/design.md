## Context

当前仓库已经完成多资产入口边界的第一轮清理，但正式可运行的数据链和研究主线仍然只覆盖 A 股个股。数据库侧当前 `pit_security_master` 与 `pams_ohlcv_daily_v2` 仍是股票口径，前端研究页默认展示“股票池”语义，运行时也默认复用 A 股个股过滤与成交规则。与此同时，最近的 `CSI1000 PIT` 解释性检查已经显示，小盘个股在当前 `POST_CLOSE -> NEXT_OPEN -> T+1` 壳下存在明显的执行脆弱性，而 ETF 更符合“个人多资产趋势配置系统”的核心暴露表达。

这次 change 的范围横跨数据库、运行时入口、前端页面和研究配置，属于跨模块 L3 设计，需要先明确边界，避免把 ETF 接入做成第二套平行系统，或者反向污染现有 A 股个股主线。

## Goals / Non-Goals

**Goals:**
- 为 A 股 ETF 建立新的正式 `cn_etf` 资产范围，并让数据库、运行时、前端页面都能显式识别该资产范围。
- 在不污染 A 股个股 `V2 canonical` 主链的前提下，新增 ETF 的最小数据库真值层，覆盖首批 9 只 ETF 的基础资料与日线研究数据。
- 为研究台提供最小 ETF 研究入口，支持单标的 `CUSTOM` 和受控预设组合，能直接发起 ETF 回测与 A/B 对照。
- 保持现有 A 股个股 baseline 逻辑不变，确保 ETF 接入有清晰的回退面和独立审计口径。

**Non-Goals:**
- 不在本轮把 ETF 做成全市场、全品类、全自动同步平台。
- 不把 ETF 混入 `pit_security_master + pams_ohlcv_daily_v2` 的股票主链，不修改现有个股 PIT 与股票侧审计逻辑。
- 不在本轮引入 ETF 专属组合构建逻辑、跨 ETF 轮动策略或防守层总配置器。
- 不在本轮强行解决 ETF 分红再投资的完整总收益链路；第一阶段以可执行价格研究为主，并显式暴露覆盖与口径限制。

## Decisions

### 1. 新增 `cn_etf` canonical asset scope，而不是把 ETF 继续挂在 `cn_a_equity`

**Decision**
- 新增 `cn_etf` 作为正式资产范围。
- `cn_etf` 共享中国大陆交易日历与 `T+1 / NEXT_OPEN / lot=100` 执行壳，但不继承股票专属过滤与股票池语义。
- `assetContext` 中显式暴露 `asset_scope='cn_etf'`、`asset_family='fund'`、`asset_class='etf'`。

**Why**
- 这次要同时接入股票 ETF、黄金 ETF、债券 ETF。继续挂在 `cn_a_equity` 下会让资产边界和交易规则再次混淆。
- 现有 A 股入口已经完成“未支持资产不得伪装成 A 股”治理，ETF 继续借壳 `cn_a_equity` 会破坏这条边界。

**Alternatives considered**
- 复用 `cn_a_equity`：改动小，但会把 ETF 与股票过滤、Universe 文案、研究审计混在一起，不可接受。
- 再细分成 `cn_equity_etf / cn_bond_etf / cn_commodity_etf` 三个 scope：长期可能合理，但对这轮“最小研究入口”来说过重。

### 2. ETF 数据库采用独立真值表，而不是写入股票 `V2 canonical`

**Decision**
- 新增独立 ETF 目录和表，而不是把 ETF 行混入股票主表。
- 最小表设计分为三层：
  - `pit_cn_etf_master`：受控 ETF 资产目录，仅纳入首批 9 只 ETF
  - `pams_cn_etf_daily`：ETF 日线真值表，包含执行所需 OHLCV 与最小元信息
  - `cn_etf_data_coverage_daily`：覆盖/刷新摘要，用于研究页和审计

**Why**
- 当前 `pit_security_master` 和 `pams_ohlcv_daily_v2` 的许多消费方默认“表里全是股票”。直接混入 ETF 会把现有 A 股 resolver 和过滤规则拖进一轮高风险回归。
- 独立 ETF 表能把回退、核对和口径说明都保持清晰。

**Alternatives considered**
- 扩展 `pit_security_master` 与 `pams_ohlcv_daily_v2` 支持 ETF：长期可能值得做，但这轮风险太高。
- 临时 CSV 文件 + 前端直读：违背数据库真值层和可复现原则，不接受。

### 3. 首批接入名单固定为 9 只 ETF，采用“受控白名单”而不是全市场扫描

**Decision**
- 第一阶段只接入以下 9 只：
  - 第一批：`510300.SH`、`510500.SH`、`510050.SH`、`518880.SH`、`511010.SH`、`512100.SH`
  - 第二批：`512890.SH`、`588000.SH`、`159915.SZ`
- 数据刷新、研究入口和前端预设都只面向这 9 只。

**Why**
- 用户已经明确希望第一批和第二批同时接入；同时受控白名单可以避免这次变更滑向“ETF 全市场平台化”。
- 这 9 只已经覆盖核心权益、中盘、小盘、红利、科技成长、黄金、国债，足够支撑第一阶段多资产研究。

**Alternatives considered**
- 全市场 ETF 自动接入：不符合“最小改造”。
- 每个指数保留多只重复 ETF：会把流动性、管理人和代码差异一并引进，不利于第一阶段归因。

### 4. 最小研究入口采用 `CUSTOM + ETF 预设组`，不新造 ETF Universe 大模式

**Decision**
- 运行时对 `cn_etf` 只支持两种正式入口：
  - `CUSTOM`：单只或少量 ETF 手工输入
  - `ETF preset group`：由前端和编译层展开成白名单 symbol 列表
- 不新增 `ALL_ETF`、`ETF_STYLE` 等大模式。

**Why**
- 这条路径改动最小，能直接复用现有回测入口、study runner 和 artifact 流。
- ETF 第一阶段的研究重点是“单资产暴露能否替代个股 PIT 风格暴露”，不是先做复杂的 ETF universe resolver。

**Alternatives considered**
- 新建 ETF 专属 Universe mode：会把范围扩大到 resolver、前端、study schema 全链，超出本轮最小目标。

### 5. ETF 研究配置必须脱离股票专属过滤，并以 ETF 口径显示在前端

**Decision**
- `cn_etf` 下禁用或隐藏以下股票专属控件与配置：
  - `exclude_st`
  - `exclude_suspended`
  - `min_list_days` 的股票上市语义
  - 股票 `industry filter`
  - `PIT constituent` 文案
- 新增 ETF 页面提示：
  - 当前 ETF 名单/批次
  - 数据覆盖起止日期
  - 数据是否仅为可执行价格口径

**Why**
- ETF 继续显示“股票池 / ST / 行业 / 成分股 PIT”会制造明显错误的研究语义。
- 这次变更必须让前端在入口层就讲真话。

### 6. 最小研究主线保持 `V10.2` 壳，不改 baseline 逻辑，只新增 ETF 研究 preset

**Decision**
- 不修改 `baseline_V10.2` 的正式主逻辑。
- 新增一个 ETF 研究 preset 族：
  - `cn_etf_single_asset_template`
  - `cn_etf_first_wave_core`
  - `cn_etf_first_wave_all`
- 这些 preset 复用现有实验总线、产物协议和结果页，但 `run_meta` 必须新增 ETF 专属元信息：
  - `asset_scope`
  - `etf_batch`
  - `etf_symbols`
  - `coverage_start/end`
  - `price_series_semantics`

**Why**
- 这轮目标是“先让 ETF 能在当前研究总线上被干净地研究”，不是重写策略壳。
- 这样最容易做 A/B：`CSI800 PIT`、`CSI1000 PIT`、`CSI1000 ETF` 能共用同一产物协议对照。

### 7. ETF 价格口径第一阶段以可执行行情为主，并显式暴露“不等于完整总收益”

**Decision**
- 第一阶段 ETF 日线表以可执行价格序列为真值，研究页和 `run_meta` 必须显式暴露 `price_series_semantics`。
- 若某些 ETF 缺少完整分红再投资链，系统 SHALL NOT 把其描述成“总收益完整复权”。

**Why**
- 这轮核心问题是验证 ETF 作为多资产主线入口是否比个股 PIT 更合适，优先级高于一步到位做完基金总收益重建。
- 只要口径被显式声明且不和股票主线混淆，第一阶段研究仍然可用、可审计。

## Risks / Trade-offs

- **[Risk] ETF 独立表会带来一套新的数据库路径** → **Mitigation**：范围仅限 9 只白名单 ETF，且不复制个股 V2 的复杂治理链，只保留最小真值与覆盖摘要。
- **[Risk] `cn_etf` 会让 asset scope 增加复杂度** → **Mitigation**：只新增一个 scope，不再细分 equity/bond/gold ETF 子 scope； instrument 语义用目录元数据承载。
- **[Risk] 前端同时接入两批 ETF 会让入口变复杂** → **Mitigation**：页面上只暴露受控预设组与单标的输入，不做无限扩展的 ETF 列表管理器。
- **[Risk] ETF 价格口径不完整会误导收益比较** → **Mitigation**：在 `run_meta`、页面提示和研究摘要中显式标注价格语义与覆盖边界。
- **[Risk] 把 ETF 放进现有 baseline 壳可能出现不适配参数** → **Mitigation**：第一阶段只定义为“研究 preset”，不升格为正式 baseline，不把研究结果直接写回主线结论。

## Migration Plan

1. 先建 ETF 独立表和白名单目录，补最小同步/导入脚本与覆盖摘要。
2. 再新增 `cn_etf` 资产范围、运行时入口和 resolver `CUSTOM/preset` 路由。
3. 然后改桌面页，让 ETF 入口、文案、配置导出与 snapshot 都能显式区分 ETF。
4. 最后补 ETF 研究 preset 与第一轮 A/B 验收脚本。

**Rollback**
- 回退 `cn_etf` 资产范围、resolver 和前端入口改动即可恢复当前系统行为。
- ETF 数据表独立存在，不会影响现有个股 `V2` 表；必要时可以整表删除或停止消费。

## Open Questions

- 第一阶段 ETF 数据源是否全部走 Tushare，还是允许个别 ETF 用交易所公开数据补齐上市日期与基础资料。
- `cn_etf` 默认 benchmark 是否保留为空，还是为研究入口提供按 ETF 类型派生的默认 benchmark。
- 第一阶段是否允许 `core batch` 做轻量等权组合，还是严格限制在单标的 study。
