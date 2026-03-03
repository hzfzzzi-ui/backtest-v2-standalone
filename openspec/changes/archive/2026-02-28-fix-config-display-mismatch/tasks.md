## 1. 后端：run_config.json 追加 resolved_universe

- [x] 1.1 在 `experiment_runner.py` 的 `resolve_universe_by_mode()` 返回后，将 `_resolved_universe` 字段追加到 `cfg_merged` 并重写 `run_config.json`
  - DoD：`run_config.json` 包含 `_resolved_universe.mode`、`resolved_count`、`raw_count` 三个字段
  - 验证：运行 ALL_A 模式回测，检查 `run_config.json` 中 `_resolved_universe.resolved_count > 0` 且 `universe.symbols` 仍为 `[]`

## 2. 前端：摘要栏标的数量修正

- [x] 2.1 修改 `renderSummaryBar()` 中"标的 N 个"的取值逻辑，优先从 `state.active_artifacts.run_meta.universe.raw_count` 读取，回退到 `config_draft.universe.symbols.length`
  - DoD：摘要栏展示的标的数量与实际回测 universe 一致
  - 验证：运行 ALL_A 模式回测，摘要栏应显示实际标的数（如 751），而非 0

## 3. 前端：实验详情标的数量修正

- [x] 3.1 修改实验配置详情表中"标的数量"行，优先使用 `run_meta.universe.raw_count`，回退到 `uniSymbols.length`
  - DoD：实验详情表"标的数量"与实际回测 universe 一致
  - 验证：点击实验历史中的配置详情，"标的数量"应显示实际 resolved 数量

## 4. Docker 构建与端到端验证

- [x] 4.1 Docker 重新构建后端，运行一次 ALL_A 模式回测，验证 `run_config.json` 包含 `_resolved_universe`，前端摘要栏和实验详情表标的数量正确
  - DoD：后端产物和前端展示均反映实际标的数量
  - 验证：对比 `run_config.json._resolved_universe.resolved_count` 与 `run_meta.json.universe.raw_count`，两者一致
