## Context

当前系统已经有一套共享的 `universe.filters` 过滤链路，覆盖 ST、停牌、上市天数、流动性、涨跌停与价格过滤。A 股 universe 解析后的过滤主要集中在 `backend/core/universe/hs300_csi500.py`，而运行期还存在两条与股票池口径直接相关的路径：

- 数据 bundle 构建阶段会基于 universe 结果生成候选集合与可交易集合。
- 实盘/回测运行期会通过 runtime data access 重新消费 universe 结果。

这意味着“科创板过滤”不是单点 UI 功能，而是一个会影响股票池、可交易池和验证结果的一致性改动。如果只在前端草稿或某个单独入口做裁剪，会产生三类问题：

- 配置草稿、验证接口和真实执行的股票池口径可能不一致。
- `baseline_V10.1` 可能在无显式选择时被悄悄改变。
- 审计信息无法说明过滤是否真正生效。

现有 `pit_security_master` 读取接口未稳定暴露板块字段，因此本次实现不能依赖新增数据库字段或大规模 provider 改造；需要在当前数据约束下以最小改动接入。

## Goals / Non-Goals

**Goals:**

- 在 `universe.filters` 新增显式的 `exclude_star_market` 开关，默认值为 `false`。
- 让验证接口、bundle 构建与运行期股票池消费同一套科创板过滤语义。
- 保持现有 baseline 默认行为不变，只有显式开启时才排除科创板标的。
- 复用现有 `excluded_counts`、`filters_config` 等元数据，保证过滤是否生效可观测、可审计。
- 补齐前后端配置协议与定向测试，避免字段漂移。

**Non-Goals:**

- 不修改 `baseline_V10.1` 默认配置。
- 不重构现有 universe/filter 全链路结构。
- 不引入新的数据库字段、独立 API 或新的板块分类服务。
- 不在本次改动中同时处理创业板、北交所或其他板块过滤。

## Decisions

### 决策 1：新增显式字段 `universe.filters.exclude_star_market`，默认关闭

原因：

- 这是对股票池口径的直接调整，必须可配置、可审计，不能隐藏在 symbol 列表预处理里。
- 默认关闭可以保证旧配置、旧 baseline 与现有回测结果保持语义一致。

备选方案：

- 直接在某个 A 股模式下默认排除科创板。
  - 否决原因：会修改既有口径，且用户无法从配置层明确感知。
- 新增单独的 `universe.exclude_boards` 列表。
  - 否决原因：当前只需要单个高价值开关，列表化会扩大协议面，增加前后端和测试负担。

### 决策 2：以“共享后端过滤 helper”统一静态候选过滤与动态 universe 裁剪

原因：

- `apply_universe_filters()` 当前已负责大部分共享过滤逻辑，但动态 universe 路径会跳过部分静态候选过滤。
- 如果只在 `apply_universe_filters()` 中实现科创板排除，动态路径可能仍保留科创板股票，导致验证与真实执行不一致。
- 把“按 symbol 级别排除科创板”的逻辑抽成共享 helper，可让候选 DataFrame 过滤和 symbol 列表裁剪共用同一口径。

设计落点：

- 在 `backend/core/universe/hs300_csi500.py` 中新增科创板识别 helper。
- `build_candidates_from_ohlcv()` 生成 `is_star_market` 列，供 DataFrame 过滤使用。
- `apply_universe_filters()` 在启用时写入 `EXCLUDE_STAR_MARKET` 计数。
- `data_bundle_builder.py` 与 `runtime_data_access.py` 在 dynamic universe 路径中复用 symbol 级 helper，确保实际可交易列表与元数据一致。

备选方案：

- 仅在 `data_bundle_builder.py` 做一次性裁剪。
  - 否决原因：运行期路径不会自动受益，仍然存在口径分叉。
- 仅在前端提交前剔除科创板代码。
  - 否决原因：前端不能成为研究口径唯一真相，也无法覆盖非前端入口。

### 决策 3：科创板识别采用“标准化 symbol 前缀规则”，不依赖 provider 元数据扩展

原因：

- 当前 security master 接口未稳定提供交易板块字段。
- 科创板 A 股主代码在现有 A 股 symbol 规范下可通过 `688xxx.SH` 以及科创板 CDR `689xxx.SH` 前缀稳定识别。
- 该方法改动范围小，易于测试，也便于后续在 provider 提供更强元数据后平滑替换。

约束：

- helper 必须先做 symbol 标准化或兼容常见内部格式，避免 `sh688001`、`688001.SH` 等格式差异导致误判。
- 识别逻辑要封装到单点函数，不允许在多个模块散落前缀判断。

备选方案：

- 扩展 `pit_security_master` 读取字段后按交易板分类。
  - 否决原因：会引入更大的数据层改造，不符合本次最小改动目标。

### 决策 4：前端只负责透传与回填，不在前端重算过滤逻辑

原因：

- 仓库明确禁止在前端重算核心研究逻辑。
- 前端唯一职责是提供显式配置入口，并确保 `buildConfigDraft()` 与 `applyConfigToUI()` 往返一致。

实现要求：

- 在基础过滤区域新增单一 checkbox。
- 草稿构建、语义 schema、运行时编译全链路保留该字段。
- 默认值为空或 `false` 时不得生成会改变旧行为的额外副作用。

## Risks / Trade-offs

- [风险] 科创板识别依赖 symbol 前缀，若未来数据源引入新的内部编码格式，可能出现漏判或误判。  
  → Mitigation：封装单点 helper，并补充不同 symbol 格式的单元测试；未来若 provider 暴露板块字段，只替换 helper 实现。

- [风险] 动态 universe 路径与静态候选过滤路径行为不一致。  
  → Mitigation：复用同一个 symbol 级过滤 helper，并在 `data_bundle_builder`、`runtime_data_access` 各补一条定向测试。

- [风险] 前后端协议新增字段后，旧草稿回填或编译链路出现字段漂移。  
  → Mitigation：在 schema、runtime compile、UI harness 中分别补回归测试，验证默认缺省时行为不变。

- [权衡] 本次沿用现有元数据结构，不单独新增复杂诊断产物。  
  → Mitigation：优先利用 `excluded_counts` 与 `filters_config` 确认功能生效；若后续需要更细颗粒度审计，再单独立项扩展诊断产物。

## Migration Plan

1. 先补 OpenSpec delta specs 与 tasks，明确字段语义和前后端责任边界。
2. 后端先实现共享 helper 和运行路径接入，保证股票池口径一致。
3. 再补前端 checkbox、草稿构建与回填逻辑。
4. 补单元测试与前端回归测试，重点验证“默认关闭不变、开启后排除科创板”。
5. 若上线后发现误判，可直接将 `exclude_star_market` 恢复为默认关闭，或回滚 helper 接入点；因为默认值不变，回滚成本低。

## Open Questions

- 当前是否需要在结果报告或 UI 诊断面板中显式展示“科创板过滤已开启”。本次先依赖现有元数据，不额外扩展展示字段。
- 若后续用户提出“多板块组合过滤”，是否升级为通用 board filter 列表。当前不提前抽象，避免过度设计。
