## Context

当前公开真相已经稳定为：
- 运行：`config_json -> experiment_id`
- 读取：`experiment_id -> manifest -> declared artifacts`

但 `backtest_v2.py` 仍残留一小批旧表面：
- `/api/backtest_v2/results/{run_id}` 读取 `report.json/report_summary.json/...`
- `_read_result()` 组装 legacy payload
- `_resolve_experiment_dir()` 仍支持 `results_dir -> latest fallback`
- `_preview_rejected_fields()` 已空转
- `_load_runtime_cfg_obj()` 已被 shared db boundary 取代

这些代码已经不再服务当前主表面，且 grep 结果显示没有 live caller。

## Goals / Non-Goals

**Goals:**
- 删除无 live caller 的公开旧壳
- 保持主表面与基线结果不变
- 用 wave1 ledger 明确“删了什么、为什么现在能删”

**Non-Goals:**
- 本 change 不删除 internal helper 对 `results_dir` 的支持
- 本 change 不改 experiment history / compare / report 主消费面
- 本 change 不处理仍有 live caller 的 shim

## Decisions

### D1: wave1 只删无 live caller 的公开旧壳

本 wave 仅处理 `backtest_v2.py` 里已确认没有 live caller 的旧路由和 helper。

选择理由：
- 风险最小
- 和 `v2-legacy-retirement-wave1` 的证据化删除策略一致

### D2: `/results/{run_id}` 直接删除，不保留 stub

该路由已经偏离当前主表面，继续保留只会制造第二套读取真相。

选择理由：
- 公开读取面必须只有 `experiment_id + manifest`
- 保留 stub 没有长期价值

### D3: internal `results_dir` 能力暂不删除

`_experiment_surface.py` 与 `internal_script_helper.py` 仍存在 internal-only `results_dir` 解析用途，本 wave 不触碰。

选择理由：
- 先删公开旧壳，再删 internal shim，风险更可控

## Risks / Trade-offs

- [风险] 存在未发现的外部调用者仍访问 `/api/backtest_v2/results/{run_id}`
  -> Mitigation：先做 caller 盘点并在 ledger 中写清“零 live caller”证据；本 wave 仅删这一条公开旧路由

- [风险] 删除 helper 时误删仍被其他函数隐式依赖的路径
  -> Mitigation：先 grep 引用，再跑 py_compile + 定向 harness + baseline gate

## Migration Plan

1. 固化 wave1 删除证据
2. 删除 `/results/{run_id}` 与 `_read_result()`
3. 删除无 caller 的空转 helper
4. 更新测试与 ops ledger
5. 运行 baseline regression gate

回滚策略：
- 若发现 live caller，则恢复该路由与 helper，不触碰已完成的 boundary freeze
