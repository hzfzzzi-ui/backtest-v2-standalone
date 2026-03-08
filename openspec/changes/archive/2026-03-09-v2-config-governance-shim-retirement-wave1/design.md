## Context

当前 saved config record 的规范化、读写与 runtime config source resolution 都放在 `_config_governance.py` 中。该文件不是公开路由，但仍位于 endpoint 层。

这与当前收敛目标冲突：

- 共享 config access 逻辑应位于 core/shared
- `_experiment_runner_api.py` 与 `internal_script_helper.py` 不应依赖 endpoint helper
- 本 wave 必须只做边界清理，不改变公开 config API 行为和基线回测结果

## Goals / Non-Goals

**Goals**
- 下沉 `_config_governance.py` 到 core shared helper
- 删除 `_config_governance.py`
- 保持 config save/load/list 与 runtime config resolution 行为不变

**Non-Goals**
- 本 wave 不删除 `/_api/backtest_v2/configs*` 公开 surface
- 本 wave 不重写 builtin config 列表逻辑
- 本 wave 不改变 `config_json` 公开真相

## Decisions

### D1: 新建 core helper 承载 saved config access

新增 `backend/core/tools/saved_config_access.py`，承载：

- `normalize_saved_config_record`
- `create_saved_config_record`
- `write_saved_config_record`
- `load_saved_config_record`
- `resolve_runtime_config_source`
- `saved_config_meta_view`

### D2: 保持 `_config_store.py` 公开行为不变

`_config_store.py` 仍继续提供 `/api/backtest_v2/configs*`，只是改用 core helper。

### D3: 删除后用 source-level guard 防回流

增加 targeted test，要求：

- `internal_script_helper.py` 不再 import endpoint `_config_governance`
- active backend source 不再引用 `_config_governance`

## Risks / Trade-offs

- [风险] config hash / normalize 行为偏移导致 config provenance 漂移
  - Mitigation: 原样迁移 helper 逻辑；跑 baseline compare
- [风险] builtin config refresh 行为变化
  - Mitigation: 保持 `_config_store.py` 只换 import，不改 builtin 逻辑
- [风险] seemingly unrelated helper relocation 误伤主链
  - Mitigation: direct harness + baseline gate

## Migration Plan

1. 固化 wave1 live caller 与删除前置条件
2. 新建 core helper 并迁移 live callers
3. 删除 `_config_governance.py`
4. 补回流测试与 ops ledger
5. 跑 baseline regression gate
