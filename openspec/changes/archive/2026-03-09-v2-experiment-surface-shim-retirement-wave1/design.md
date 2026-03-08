## Context

当前实验目录和 manifest 访问逻辑分散在 `_experiment_surface.py` 中。该文件不再承载公开路由，但仍被 core helper 间接依赖。

这与当前目标冲突：

- 共享实验产物访问逻辑应位于 core/shared 层
- API endpoint 模块不应成为 core helper 的依赖源
- 删除 wave 必须只做边界清理，不改变实验结果和公开 manifest 协议

## Goals / Non-Goals

**Goals**
- 把共享 experiment/manifest/artifact path helper 下沉到 core
- 删除 `_experiment_surface.py`
- 保持 manifest 驱动读面与 internal script helper 行为不变

**Non-Goals**
- 本 wave 不删除 `results_dir` internal-only 能力
- 本 wave 不改 experiment history 的公开 API 协议
- 本 wave 不动回测计算核、artifact writer、数据库访问逻辑

## Decisions

### D1: 新建 core helper 承载 experiment artifact access

新增 `backend/core/tools/experiment_artifact_access.py`，承载：

- experiments_root
- resolve_experiment_dir_by_id
- resolve_experiment_dir_from_results_dir
- load_manifest
- manifest_declared_paths
- manifest_artifact_rel
- resolve_declared_artifact_path
- experiment_surface_flags

### D2: API 与 internal helper 全量迁移后再删 shim

只有在三个 live caller 都迁移完成后，才删除 `_experiment_surface.py`。

### D3: 删除后用 source-level guard 防回流

增加 targeted test，要求：

- `backend/core/tools/internal_script_helper.py` 不再引用 `backend.api.endpoints._experiment_surface`
- active backend source 不再引用 `_experiment_surface`

## Risks / Trade-offs

- [风险] 路径 helper 下沉后行为偏移，影响 manifest/artifact 读取
  - Mitigation: 保持函数签名和行为一致；直跑 router/harness
- [风险] 删除 shim 后遗漏隐式调用者
  - Mitigation: grep 全仓引用、增加 no-reference guard
- [风险] seemingly unrelated helper relocation 误伤基线产物链路
  - Mitigation: baseline regression gate 必跑

## Migration Plan

1. 固化 wave1 caller 证据
2. 新建 core helper 并迁移 live callers
3. 删除 `_experiment_surface.py`
4. 增加回流测试与 ops ledger
5. 运行基线门禁
