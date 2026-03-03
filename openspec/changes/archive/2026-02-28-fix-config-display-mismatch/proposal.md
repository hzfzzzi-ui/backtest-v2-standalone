## Why

`run_config.json` 在 universe 扩展**之前**写入磁盘（experiment_runner.py:119-120），保存的是未解析的输入配置。当 `universe_mode = ALL_A / INDUSTRY` 等非 CUSTOM 模式时，`symbols` 字段为空数组 `[]`（或 CUSTOM 回退后的 3 个默认标的），但实际回测可能跑了 400–800 只股票。前端摘要栏和实验历史详情页直接读取 `run_config.json` 中的 `symbols.length` 来展示"标的 N 个"，导致用户看到的数字与实际回测范围严重不符。`run_meta.json` 中的 `universe_meta` 正确记录了扩展后的 universe 信息，但前端未使用该数据。

## What Changes

- **后端**：在 universe 解析完成后，将实际使用的 symbols 列表回写到 `run_config.json`，使该文件反映真实运行参数而非输入参数
- **前端摘要栏**：`renderSummaryBar()` 中"标的 N 个"改为优先从 `run_meta.universe` 获取实际标的数量，回退到 `config_draft.universe.symbols.length`
- **前端实验详情**：实验配置详情表的"标的数量"行优先使用 `run_meta.universe.resolved_count`，而非直接 `symbols.length`

## Capabilities

### New Capabilities

（无新增能力）

### Modified Capabilities

- `single-run-pipeline`: run_config.json 写入时机从"universe 解析前"变更为"universe 解析后"，包含实际 resolved symbols

## Impact

| 文件 | 变更 |
|------|------|
| `backend/core/tools/experiment_runner.py` | 将 `run_config.json` 写入移到 universe 解析之后，symbols 字段更新为 resolved 列表 |
| `frontend/assets/js/backtest_v2.js` | `renderSummaryBar()` 和实验配置详情表读取 `run_meta.universe` 展示实际标的数量 |
