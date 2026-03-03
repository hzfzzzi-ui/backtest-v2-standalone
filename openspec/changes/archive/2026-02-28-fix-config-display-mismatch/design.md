## Context

`experiment_runner.run_experiment()` 当前在 universe 解析**之前**（line 119-120）将 `cfg_merged` 写入 `run_config.json`。此时 `cfg_merged.universe.symbols` 仍是用户输入值（非 CUSTOM 模式通常为 `[]`）。Universe 解析在 line 140-148 发生，返回实际 `(symbols, universe_meta)` 元组，但这些信息只写入 `run_meta.json`（通过 `backtest_v2_artifacts.py`），不会回更新 `run_config.json`。

前端有两处直接读取 `symbols.length`：
1. `renderSummaryBar()`（line 736）：`config_draft.universe.symbols.length` → "标的 N 个"
2. 实验详情 `renderExperimentConfigDetail()`（line 2216-2228）：`universe.symbols.length` → "标的数量"

两处都未查看 `run_meta.universe`，导致展示值与实际不符。

## Goals / Non-Goals

**Goals:**
- `run_config.json` 反映实际运行参数，而非原始输入（"唯一真相"原则）
- 前端"标的数量"展示正确的 resolved 数量
- 变更不影响 CUSTOM 模式（用户手选标的时 symbols 本就正确）

**Non-Goals:**
- 不修改 `resolve_universe_by_mode()` 返回结构
- 不改变 `run_meta.json` 的写入逻辑（它已正确包含 universe_meta）
- 不在 `run_config.json` 中存储完整 symbol 列表（对 ALL_A 800+ symbol 来说文件过大且无必要）

## Decisions

### D1: 后端 — 在 run_config.json 中追加 resolved_universe 摘要

**方案 A（采用）**：universe 解析后，在已写入的 `cfg_merged` 中追加 `_resolved_universe` 字段再写一次：
```python
cfg_merged["_resolved_universe"] = {
    "mode": universe_mode,
    "resolved_count": len(symbols),
    "raw_count": universe_meta.get("raw_count", len(symbols)),
}
tmp_cfg.write_text(json.dumps(cfg_merged, ...))
```
- 优点：单次追加写入、不改变 `cfg_merged` 原始结构、字段以 `_` 前缀标识为派生数据
- 优点：保留完整输入配置（可追溯用户原始意图），同时补充运行时解析结果

**方案 B（弃用）**：将 `run_config.json` 写入整体延后到 universe 解析后，直接覆盖 `symbols` 字段。
- 缺点：`load_config()` 在 line 122 依赖 `tmp_cfg` 文件路径，写入必须在其之前
- 缺点：覆盖 `symbols` 后无法区分"用户输入"与"系统解析"

### D2: 前端 — 优先使用 run_meta.universe 展示标的数量

`run_meta.json` 已经包含 `universe.raw_count` 字段。前端在加载实验结果后，`state.active_artifacts.run_meta` 可获取。

- `renderSummaryBar()`：优先从 `run_meta.universe.raw_count` 取值，回退到 `config_draft.universe.symbols.length`
- `renderExperimentConfigDetail()`：同上逻辑，优先 `run_meta.universe.raw_count`

### D3: 保留 run_config.json 初始写入时机不变

`load_config(str(tmp_cfg))` 依赖磁盘上的配置文件。因此初始写入（line 119-120）不能删除。采用"先写后追加"策略：初始写入后，universe 解析完成后追加 `_resolved_universe` 字段再次写入。

## Risks / Trade-offs

- **风险**：`run_config.json` 被写入两次（初始 + 追加）。如果 universe 解析失败（抛出异常），文件中将不含 `_resolved_universe`。→ **缓解**：这是可接受的——异常时整个实验失败，不会产生误导性产物。
- **风险**：前端 `run_meta` 可能未加载（如旧实验无 `run_meta.json`）。→ **缓解**：回退到 `symbols.length`，行为与修复前一致，不会更差。
- **trade-off**：`_resolved_universe` 使用下划线前缀表示派生字段，与 `cfg_merged` 原始配置混合。→ 可接受，JSON 无 schema 约束，前缀足以区分。
