# Design

## Baseline Contract

- 锁定底座不是原始 baseline `exp_20260307_051743747_77d8`，而是当前 formal candidate `exp_20260307_171750033_eb7b`。
- 新 candidate 只允许相对该底座发生一个主改动：
  - `strategy.params.breakout_window: 55 -> 35`
- 其他 runtime 语义必须保持一致：
  - `atr_stop_k=1.0` 底座不回退
  - 股票池 `HS300_ZZ500`
  - 区间 `2016-03-01 ~ 2026-03-01`
  - benchmark `000300.SH`
  - 成本、执行、评价口径不变

## Candidate Exposure

新增独立 candidate 名称：

- `v2-breakout-br35-atr10-candidate`

这样做而不是替换旧 candidate，有两个目的：

1. 保留旧 `ATR1.0` candidate 的可复现 identity 和证据链。
2. 让 `BR35+ATR1.0` 成为可独立回退、可独立审计的新 formal candidate。

## Evidence Bundle

新 candidate 的证据包由两部分组成：

- `breakout_window_research_20260307_190247`
- `breakout_window35_robustness_20260307_191748`

它们共同覆盖：

- 全样本对照
- 局部稳健性
- 分阶段表现
- 终点敏感性
- 集中度检查

## Frontend Integration

前端分两条入口：

1. `preset` 入口
- 顶部 preset 下拉新增 `BR35 + ATR1.0`。
- 该入口继续走 locked candidate 路径，忽略页面草稿。

2. `load config` 入口
- 通过 builtin config store 自动生成 `BR35+ATR1.0+CSI800+10Y`。
- 前端“加载”继续复用 `GET /api/backtest_v2/configs` 和 `GET /api/backtest_v2/configs/{id}`，不增加新协议。

## Verification

完成实现后需要验证：

1. 新 preset 返回 `resolved_config_mode=locked_candidate` 且 `run_meta.candidate.candidate_name` 正确。
2. 新 builtin config 出现在前端加载列表中，并能正确回填 UI。
3. 运行结果产物包含 `candidate_summary.json/.md` 与 `candidate_provenance.json`。
4. 容器重启后 API 仍能返回上述结果。
