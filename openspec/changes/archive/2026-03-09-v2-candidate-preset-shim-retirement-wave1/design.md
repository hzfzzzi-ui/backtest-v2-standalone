## Context

locked candidate preset 的定义、审计和 artifact writer 仍在 `_candidate_presets.py` 中。该文件本质是 shared helper，而非公开 API。

## Goals

- 下沉 `_candidate_presets.py` 到 core helper
- 删除 endpoint shim
- 保持 locked candidate preset 行为不变

## Non-Goals

- 本 wave 不改变 locked candidate preset 列表
- 本 wave 不改变 locked candidate 产物协议
- 本 wave 不动普通回测主链

## Decisions

### D1: 新建 core helper 承载 locked candidate preset access

新增 `backend/core/tools/locked_candidate_presets.py`，承载：

- `is_locked_candidate_preset`
- `build_locked_candidate_cfg`
- `write_locked_candidate_artifacts`
- 相关 assess/load helper

### D2: endpoint 与 internal helper 全量迁移后再删 shim

只有 `_experiment_runner_api.py` 与 `internal_script_helper.py` 全部改用 core helper 后，才删除 `_candidate_presets.py`。

## Risks

- helper relocation 误伤 locked candidate branch
- 静态 T+1 guard 行为偏移
- seemingly unrelated shim 删除影响 baseline

## Mitigation

- 保持 helper 逻辑原样迁移
- direct harness 检查 locked candidate predicate 与 helper 存在
- baseline gate 必跑
