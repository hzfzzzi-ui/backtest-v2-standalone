## Context

当前 `2007-2026` advisory 剩余 `740` 行 blocker，可拆成：

- `244` 行 `eligible_no_source = missing_in_all_sources`
- `244` 行 `pre_close_imputed_zero = source_present_low_confidence_fill`
- `244` 行 `turnover_rate_imputed_zero = missing_in_all_sources`
- `8` 行 `turnover_rate_imputed_zero = mapping_failure`

前 `732` 行全部落在 `sh600286 / sz000583 / sz000699` 三个 symbol，并且窗口都是从 `2007-01-04` 直接连续到 `delist_date`。这不是“中间缺了一小段源”，而是 formal window 起点已经落在终止边界尾段内部。

剩余 `8` 行全部落在 `bj920047 / bj920090`，原因是这两只 symbol 在 cause class 改成 `bj_pre_daily_basic_gap` 之前已经建过老版本 slice，当前行仍保留旧 build。

## Goals / Non-Goals

**Goals**

- 用最小代码改动把三只 A 股真无源尾巴收敛为显式 terminal override。
- 不放宽 runtime，不把规则泛化到其他 symbol。
- 通过定点重刷清掉 BJ 两只 symbol 的旧 `mapping_failure`。

**Non-Goals**

- 不新增通用“只要有 `delist_date` 就收口”的 heuristic。
- 不修改 `baseline`、runtime gate 或交易逻辑。
- 不重新定义 hard gate 窗口。

## Decisions

### 1. 三只 A 股只走显式 override，不改通用 heuristic

继续沿用 `OfficialTerminalOverride` registry，但这次的证据形态不是“明确的摘牌日单点”或“明确的暂停上市窄窗口”，而是：

- formal window 起点之前已有正式暂停上市证据
- canonical `delist_date` 已由 `pit_security_master / raw_tushare_stock_basic` 给出

因此 override 只覆盖：

- `sh600286`: `2007-01-04 ~ 2007-05-31`
- `sz000583`: `2007-01-04 ~ 2007-05-21`
- `sz000699`: `2007-01-04 ~ 2007-04-04`

### 2. override 仍只对原本的 `source_unresolved` 生效

这能保证：

- 不覆盖已有的 `traded / suspended_confirmed / synthetic_gap_fill`
- 只把本来就处于连续无源尾段的行收成 `delist_tail_confirmed`

### 3. BJ mapping 不改单独逻辑，只做定点重刷

`bj920047 / bj920090` 当前 `mapping_failure` 的 build_run 仍是旧 slice。规则本身已经改对，所以不新增代码分支，只需要 rebuild。

## Risks / Trade-offs

- `sz000583` 与 `sh600286` 的起点证据弱于此前 `sh600680 / sh601268` 那种纯交易所正式页面，属于“正式披露介质/公告摘要 + canonical delist_date”的组合证据。
- 为了避免 registry 失控，这次 override 仍只加三只，不做泛化。

## Rollback

- 从 `OFFICIAL_TERMINAL_OVERRIDES` 删掉三条新配置。
- 重刷 `sh600286 / sz000583 / sz000699 / bj920047 / bj920090`。
- 重跑 formal audits，确认 advisory blocker 恢复到当前基线。
