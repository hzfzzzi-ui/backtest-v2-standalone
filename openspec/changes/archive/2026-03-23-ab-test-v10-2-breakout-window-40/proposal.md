## Why

`baseline_V10.2` 当前正式参数把 `breakout_window` 固定在 `45`，但这仍是一个会直接影响入场节奏与交易密度的主旋钮。要判断 `40` 是否值得继续推进，必须在不改股票池、成本、执行时点、排序和退出规则的前提下，做一次可复现的单变量 A/B。

## What Changes

- 新增一个以 `baseline_V10_2` 为锚点的 declarative study，只比较 `breakout_window=45` 与 `breakout_window=40`。
- 通过 `research/studies/*.study.yaml` 和 generated thin script 固化实验入口，避免手工改 JSON 造成口径漂移。
- 运行 study runner 产出 A/B 两个实验结果及对比摘要，但不直接改正式 baseline 配置，也不自动升格候选参数。

## Capabilities

### New Capabilities
- `breakout-window-experiment`: 规范 V10.2 breakout window 单变量 A/B 研究的定义、执行与输出口径。

### Modified Capabilities
- 无

## Impact

- 影响目录：`research/studies/v10`、`backend/scripts/generated`、`tests/unit`、`openspec/changes/ab-test-v10-2-breakout-window-40`
- 运行产物：`outputs/experiments/*` 与 study summary 产物
- 不影响：正式 `baseline_V10_2/config.json`、主线运行默认参数、API 输出协议
