## Context

当前仓库已经具备 `cn_etf` 独立真值表、ETF 目录、ETF 覆盖摘要和 `cn_etf_first_wave_core` 研究 preset，`build_data_bundle()` 也已经能在 `asset_scope=cn_etf` 时切换到 `pams_cn_etf_daily`。但实跑发现两类口径漂移仍然存在：

- `run_config / run_meta` 会继承股票主线的 `000300.SH` 基准，而不是保持 ETF 研究入口的基准真相。
- `audit.json` 中的 `governor_budget.latest` 会退化成 `cn_a_equity + cn_stock_trend_alpha_core` 语义，和 `run_meta.governed_snapshot` 的 `cn_etf` 真相不一致。

这说明 provider/read path 已经“能跑”，但主线 truth 还没收口。当前 change 的目标不是新增 ETF 策略能力，而是把 ETF 主线接入后的运行时真相和 smoke 证据链做实。

## Goals / Non-Goals

**Goals:**

- 让 `asset_scope=cn_etf` 运行时始终从 ETF 真值表和 ETF 入口语义出发，不再静默继承股票主线默认值。
- 让 `run_meta / audit / Governor` 对同一次 ETF 主线运行输出一致的资产语义和 ETF sleeve 摘要。
- 固化一条可复现的最小 smoke run，用来验证 ETF provider/read path、runtime truth 和产物完整性。

**Non-Goals:**

- 不扩首波 ETF 名单，不增加新的 ETF 资产。
- 不改 `cn_etf_beta` 的选 ETF 策略逻辑，也不要求 smoke run 必须产生交易。
- 不把 `value_bluechip_satellite`、`insurance_overlay` 或新的 defense 资产纳入本轮。

## Decisions

### 1. 复用现有 ETF 数据链，不新增数据库对象

继续复用：

- `pit_cn_etf_master`
- `pams_cn_etf_daily`
- `cn_etf_data_coverage_daily`
- 现有 `cn_etf_first_wave_core` preset

原因：provider/read path 已经存在，当前问题不是缺链路，而是 runtime truth 漂移。重新建链只会扩大改动面。

### 2. `cn_etf` 的 benchmark truth 以 ETF 入口为准，不允许默认漏回 `000300.SH`

当 `asset_scope=cn_etf` 且研究入口未显式指定 benchmark 时，运行时应保持“ETF 研究入口未指定股票基准”这一事实；如果为了图表或比较曲线需要补一个默认 benchmark，也必须显式标记来源，而不是静默继承股票 baseline 的 `000300.SH`。

原因：当前 `run_config.json` 和 `run_meta.json` 的 `000300.SH` 会制造错误解释，后续 regime、Governor 和前端都会被错误基准污染。

### 3. Governor/latest audit 以 governed snapshot 为准，不再反推股票默认语义

`run_meta.governed_snapshot` 已经能正确反映 `asset_scope=cn_etf`。本轮要求 `audit.json.governor_budget.latest` 与之对齐，优先消费 governed snapshot 或 ETF-aware 最新日级预算，而不是退回股票 alpha 默认结构。

原因：同一次运行在 `run_meta` 和 `audit` 中说两种资产语义，会直接破坏“唯一真相”原则。

### 4. smoke run 的通过条件定义为“路径真相通过”，而不是“必须有交易”

当前 `cn_etf_first_wave_core` 在 `2016-11-04 ~ 2026-03-20` 上可以完成运行，但结果是 `0 trades`。这轮不把“ETF 研究壳是否已产生有效交易”当作主线接通判据，而只验证：

- provider/read path 正确命中 ETF 表
- `asset_scope / daily_table / coverage / benchmark_source` 正确
- `cn_etf_beta` Phase 1 摘要正确
- `audit / run_meta` 语义一致

原因：这条 change 的范围是主线接通，不是 ETF 策略有效性研究。

## Risks / Trade-offs

- [Risk] ETF 运行不显式比较 `000300.SH` 后，部分旧图表可能失去默认比较基准。  
  → Mitigation：保留 `benchmark_source` 和空 benchmark 语义，让后续前端显式处理，而不是偷偷补股票基准。

- [Risk] `audit.json` 改用 governed snapshot 后，旧的股票型默认断言可能失效。  
  → Mitigation：补定向单测，只对 `asset_scope=cn_etf` 路径改口径，不影响 `cn_a_equity`。

- [Risk] smoke run 仍然是 `0 trades`，容易被误读成“ETF 接入失败”。  
  → Mitigation：在 change 和实现说明里明确区分“路径 smoke 通过”和“策略有效性研究尚未开始”。

## Migration Plan

1. 收口 ETF benchmark/runtime truth：
   - 修正 ETF study 编译后的 benchmark 继承逻辑
   - 让 `run_meta` 暴露 ETF benchmark source
2. 收口 audit/governor truth：
   - 修正 `audit.json.governor_budget.latest` 的 ETF 资产语义
   - 对齐 `research_audit` 的 ETF entry 解释
3. 固化 smoke run：
   - 复用 `etf/cn_etf_first_wave_core`
   - 产出最小 smoke 摘要
4. 回退：
   - 可逐层撤回 runtime truth 修正、audit 对齐和 smoke 断言，数据库无需回退

## Open Questions

- ETF 主线后续是否需要显式的 ETF benchmark fallback（例如选中第一只 core beta ETF）作为图表默认对照，目前本轮只要求“说真话”，不要求固定 fallback 行为。
- 结果工作台是否要在下一条 change 中正式显示 `benchmark_source` 与“ETF smoke pass / zero-trade”标签，本轮不进入前端展示改造。
