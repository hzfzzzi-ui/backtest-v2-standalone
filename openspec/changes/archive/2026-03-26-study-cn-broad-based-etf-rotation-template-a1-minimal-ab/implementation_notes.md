## 实现范围

本轮只完成模板 A 的 A1 最小对照，不修改 ETF provider 规则骨架。

已落地内容：

- 新增 study：
  - `research/studies/etf/cn_broad_based_rotation_template_a1.study.yaml`
- A1 显式使用标准资产：
  - `159845.SZ` 标准中证1000 ETF
  - `510880.SH` 标准红利 ETF
- A1 使用共同有效覆盖窗口：
  - `2021-03-31 ~ 2026-03-25`

## 结果

主结果在：

- `outputs/ops/study_cn_broad_based_etf_rotation_template_a1_20260326/variant_compare.csv`
- `outputs/ops/study_cn_broad_based_etf_rotation_template_a1_20260326/summary.json`

A1 四组最小对照结果：

- `A1_STAR50_TOP2_CASH`
  - `CAGR 0.89%`
  - `MaxDD -22.99%`
  - `Sharpe 0.134`
  - 当前冠军
- `A1_GEM_TOP2_CASH`
  - `CAGR -1.84%`
  - `MaxDD -21.45%`
  - `Sharpe -0.155`
- `A1_GEM_TOP2_BOND`
  - `CAGR -2.26%`
  - `MaxDD -21.00%`
  - `Sharpe -0.215`
- `A1_GEM_TOP1_CASH`
  - `CAGR 0.00%`
  - `MaxDD 0.00%`
  - `Sharpe 0.000`
  - `trades = 0`

## 事实结论

1. A1 的成长位赢家从 A0 的 `159915.SZ` 变成了 `588000.SH`
2. `Top1` 在 A1 仍然直接失效，继续不适合作为模板 A 的默认组合构建
3. `511010` fallback 在 A1 标准资产池上反而劣于纯 `cash`
4. A1 冠军是 `A1_STAR50_TOP2_CASH`
5. A1 冠军仍然弱于 A0 冠军在同一重叠窗口上的结果

## A0 overlap 参考

为避免把 A1 `2021-2026` 与 A0 `2016-2026` 直接横比，本轮补了一份 A0 冠军在同一重叠窗口上的参考：

- A0 overlap 参考实验：`exp_20260326_031253456_78ea`
- 重叠窗口：`2021-03-31 ~ 2026-03-25`
- `CAGR 2.09%`
- `MaxDD -10.86%`
- `Sharpe 0.300`

这说明：

- A1 标准资产池并没有在当前模板 A 骨架上优于 A0 proxy 池
- 当前 A1 不能因为“资产更标准”就被视为更优版本

## 风险

- A1 结果只覆盖 `2021-2026`，市场环境明显短于 A0 主窗口
- `159845.SZ` 覆盖起点决定了 A1 暂时无法回到 `2016-2026`
- A1 结果说明标准资产替换会改变最优成长位和 fallback 结论，因此不能直接继承 A0 冠军配置

## 验证

已完成：

- `python -m backend.cli study_run etf/cn_broad_based_rotation_template_a1 --dry-run`
- `docker exec backtest-v2-standalone python -m backend.cli study_run etf/cn_broad_based_rotation_template_a1`
- `openspec validate study-cn-broad-based-etf-rotation-template-a1-minimal-ab --type change --strict`

## 回退

如需回退本轮，只需撤回：

- `research/studies/etf/cn_broad_based_rotation_template_a1.study.yaml`
- `openspec/changes/study-cn-broad-based-etf-rotation-template-a1-minimal-ab/`
