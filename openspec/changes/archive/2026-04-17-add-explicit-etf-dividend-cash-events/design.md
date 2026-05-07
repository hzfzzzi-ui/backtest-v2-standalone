## Context

当前 CN ETF 数据侧表只提供日线和 `adj_factor`，价格语义是 `executable_price_only_not_total_return`。运行时估值通过 `hfq_close / entry_adj * qty` 平滑除权除息，但没有显式现金分红事件；现金只会被 BUY/SELL fill 改变。  

这套混合口径在企业行为修复之后已经暴露出一个清晰缺口：像 `511010.SH` 这样的防守 ETF，分红只抬高了持仓估值，没有单独记入 `cash`，卖出时又只按原始成交价回款，链路不可审计。

约束：
- 只改 `cn_etf` 主线，不碰股票腿和统一组合逻辑。
- 保留现有“大比例 adj_factor + 价格跳空”份额折算处理，不把现金分红和份额折算混为一类。
- 继续以正式 provider / data bundle / stage pipeline 为主路径，不把分红逻辑塞到前端或 `outputs/`。

## Goals / Non-Goals

**Goals:**
- 为 CN ETF 引入正式的分红事件数据源与 provider 合同。
- 在运行时把 ETF 现金分红变成显式记账事件，支持 `ex_date` 与 `pay_date` 两种 cash 入账口径。
- 当显式分红事件生效时，中性化 HFQ 估值基线，避免一笔分红同时出现在估值和 cash 中。
- 扩展审计，使 `cash`、`receivable`、`NAV` 与事件样本都可回放、可核对。

**Non-Goals:**
- 不处理股票现金分红。
- 不改 ETF 选池、排序、state、budget 或 unified combo 研究逻辑。
- 不新增前端控件；本次只在配置层保留可选口径。
- 不顺手清洗 `openspec/specs/accounting-integrity-audit/spec.md` 的历史编码问题。

## Decisions

1. 分红事件使用独立 side table，而不是并回日线表
- 采用独立表 `pit_cn_etf_dividend_events`，字段最少包含 `event_id / ts_code / symbol / ann_date / record_date / ex_date / pay_date / div_cash / div_proc / source / build_run_id`。
- 原因：分红事件是离散 corporate action，不应污染 `pams_cn_etf_daily` 的日线粒度；独立表也更利于 provider 审计与回放。
- 备选方案：把 `div_cash` 等字段加到日线表。
  - 放弃原因：会把事件语义摊平到 bar 级别，后续到账/应收链路更难审计。

2. 运行时采用“除息确认权益，到账转现金”的双阶段模型
- 新增 `execution.dividend_cash_timing_mode`，允许 `ex_date` 或 `pay_date`。
- `ex_date` 模式：除息日直接把分红记入 `cash`。
- `pay_date` 模式：除息日记入 `dividend_receivable`，到账日再从 receivable 转入 `cash`。
- 原因：`pay_date` 更贴近可用现金现实；同时保留 `ex_date` 口径，便于研究与对照。
- 备选方案：只支持 ex-date 现金入账。
  - 放弃原因：无法表达到账前不可用现金，也与用户要求的“除息/到账口径”不一致。

3. 显式分红生效时通过 rebasing `position_entry_adj` 做估值中性化
- 在除息日处理事件时，读取前一交易日与当日的 `adj_factor`；对持仓的 `position_entry_adj` 乘上 `current_adj / prev_adj`。
- 结果：HFQ 估值只保留 ex-div 后的市值，不再把同一笔现金分红继续留在估值里。
- 原因：这样可以最小改动复用现有 `hfq_close / entry_adj * qty` 估值公式，并与份额折算逻辑分离。
- 备选方案：改写为一套 ETF 专用 total-return / price-only 双账估值引擎。
  - 放弃原因：改动面过大，不符合本次最小 L3 修复边界。

4. 审计层扩展为 `cash + receivable + market_value = nav`
- `pay_date` 模式下，NAV 包含 receivable，但 receivable 不可用于买入。
- `backtest-audit` 与 `accounting-integrity-audit` 都要显式校验：
  - `cash_after = cash_before + sell_net + dividend_cash_credit - buy_net`
  - `receivable_after = receivable_before + dividend_receivable_create - dividend_receivable_settle`
  - `nav = cash_after + receivable_after + market_value`
- 原因：只有把 receivable 放进正式审计，才能同时满足 NAV 连续性和现金可用性。
- 备选方案：在 pay-date 模式下忽略 ex-date 到 pay-date 的权益变化。
  - 放弃原因：会扭曲 NAV，与正式审计目标冲突。

## Risks / Trade-offs

- [Tushare `fund_div` 历史缺口或异常事件] → 刷新脚本保留 `div_proc`、`ann_date`、`record_date` 和事件样本，provider summary 暴露事件数与缺口。
- [显式分红与份额折算混淆] → 继续保留“大比例 adj_factor + 开盘跳空匹配”的 share transform 判定，只对小比例现金分红走 dividend path。
- [新增 receivable 后破坏旧 audit 公式] → 同步修改 audit builder 和单测，不允许旧公式静默通过。
- [非 ETF 路径被误伤] → 仅在 `asset_scope == "cn_etf"` 且存在 dividend event feed 时启用；股票主线行为保持不变。

## Migration Plan

1. 扩展 ETF 刷新脚本，落地 `pit_cn_etf_dividend_events`。
2. provider / data bundle 暴露 ETF dividend events，并把事件统计写入 summary / run_meta。
3. runtime 增加 receivable / processed event ledger，在 open fills 前处理 dividend lifecycle。
4. 扩展 NAV / audit / unit tests，确认无双重计数。
5. 重新跑 ETF 腿对照，检查 `511010` 分红窗口与总收益差异。

## Open Questions

- 暂不开放前端口径切换，本次默认值定为 `pay_date`；若后续需要 UI 暴露，再单独起展示层 change。
- Tushare 若返回 `pay_date` 为空但 `earpay_date` 有值，本次先按 `pay_date ?? earpay_date ?? ex_date` 归一；若真实数据再暴露更多边缘案例，再补专门治理。
