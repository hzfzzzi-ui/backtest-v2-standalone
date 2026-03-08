## Context

截至 `v2-legacy-retirement-wave1`：
- 公开主链已经收敛到 `config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`
- 基线门禁以 `exp_20260308_021045840_cde0` 锁定，最新复跑核心产物持续 `PASS`
- 但边界仍未完全冻结：
  - `backtest_v2.py` 公开模型仍带 `config_id/runtime_config_json/results_dir`
  - `artifacts/read` 仍接受 `results_dir` 后门
  - `backtest_v2.py` 的 benchmark/symbol/validate_data 路由仍直接创建 `PostgresDataProvider`
  - `audit.json`、`stage_summary`、`stage_pipeline` 仍分散在 foundation shell 与 artifact stabilize 里

这意味着继续删除旧代码前，public surface、database surface、audit surface 还缺最后一层制度化收口。

## Goals / Non-Goals

**Goals:**
- 冻结公开运行/预览/产物读取 API 的严格契约，并拒绝 legacy 公共字段
- 冻结 foundation shell 为唯一公开引擎编排边界
- 冻结 API 侧数据库访问为共享 boundary module，避免继续在路由里直接 `PostgresDataProvider(...)`
- 冻结审计产物归一化入口，统一 `audit.json`、`stage_summary`、`stage_pipeline`
- 在不改变 `exp_20260308_021045840_cde0` 核心结果的前提下完成上述收口

**Non-Goals:**
- 本 change 不重写 legacy execution kernel，不改交易撮合与信号计算口径
- 本 change 不批量删除 live internal shim
- 本 change 不修改 benchmark、手续费、股票池、调仓频率等研究口径
- 本 change 不做统一 archive，只为后续 retirement wave 提供冻结边界

## Decisions

### D1: 公开请求契约与内部执行请求分离

公开 API 使用新的严格模型，只暴露：
- `run/run_async`: `preset + config_json`
- `execution/preview`: `config_json + exp_id + as_of_date + top_n`
- `artifacts/read`: `exp_id + rel_path`

内部仍可保留 `BacktestV2ExperimentRequest` 作为兼容执行壳的载体，但公开路由不再直接暴露它。

选择理由：
- 这样可以把“公开真相”与“内部兼容字段”彻底分开
- 能用 `extra="forbid"` 直接阻断 legacy 字段重新进入 public surface

拒绝的备选方案：
- 继续让公开路由直接接收内部 request model，再靠 `_validate_*` 动态拒绝字段
  - 拒绝，因为模型本身仍在对外泄露错误能力边界

### D2: `results_dir` 只允许 internal helper 使用

公开产物读取只认 `exp_id + manifest declared path`。`results_dir` 仅保留在 internal helper 与内部脚本边界中使用。

选择理由：
- `results_dir` 是文件系统实现细节，不应继续成为 public API 真相
- 这能把前端依赖彻底锁到 `experiment_id + manifest`

拒绝的备选方案：
- 同时继续接受 `results_dir` 作为宽松兼容输入
  - 拒绝，因为这会长期保留 public backdoor，妨碍 retirement

### D3: 数据库访问冻结为 boundary module，而不是散布在 route 中

新增共享数据库边界模块，负责：
- runtime config/provider 创建
- benchmark/symbol 序列读取
- validation 用 runtime universe 解析与 filter snapshot
- 必要的 stock name / ST 辅助查询

选择理由：
- 主回测已通过 `DataBundleBuilder` 收口，API 侧也必须遵守同一原则
- 这样后续删除旧 provider 直连代码时，风险面会更小

拒绝的备选方案：
- 只在 `backtest_v2.py` 内做几个 helper function
  - 拒绝，因为那只是在大文件内重新堆积边界代码，不是真正冻结模块责任

### D4: 审计契约独立成模块

新增共享审计契约模块，统一：
- stage summary 归一化
- stage pipeline metadata 归一化
- `audit.json` 组装

foundation shell 只产出原始阶段信息，artifact stabilize 调用同一模块写盘。

选择理由：
- 这样 `run_meta / audit / stage_summary / manifest` 的口径来自同一真相
- 后续要继续删旧 report/compat 层时，不会再次把 audit 逻辑散出去

拒绝的备选方案：
- 保持 foundation shell 与 artifact writer 各自拼一份 audit
  - 拒绝，因为这会重新制造口径漂移

## Risks / Trade-offs

- [风险] 前端仍发送 `results_dir/workbench_mode/fast_mode` 等 legacy 字段，导致 strict model 拒绝
  -> Mitigation：同步收口前端 payload，仅保留公开契约字段

- [风险] 将验证路由的 universe/filter 逻辑迁入 boundary module 时引入口径漂移
  -> Mitigation：优先做代码搬迁而非算法改写，保留原始参数、默认值与顺序，并用 targeted harness + baseline gate 验证

- [风险] 审计 contract 重组后影响 `manifest/run_meta/audit.json` 字段顺序或缺字段
  -> Mitigation：新增定向测试，要求关键字段存在且与当前 schema 对齐

- [风险] 公开 `results/{run_id}` 老入口仍可能有未知外部调用者
  -> Mitigation：本 change 不强删该路由，先把新的公开真相锁死；真正删除放后续 retirement wave

## Migration Plan

1. 先建立 `v2-backend-boundary-freeze` 的 public contract / db boundary / audit contract
2. 让 `backtest_v2.py` 和 `_experiment_runner_api.py` 公开路由切到新 contract
3. 让 benchmark/symbol/validate_data 路由切到共享 db boundary
4. 让 foundation shell 与 artifact stabilize 共享同一 audit contract
5. 补 targeted tests 与 freeze 文档
6. 运行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`

回滚策略：
- 如果 public strict contract 误伤现有前端，则回滚公开模型与前端 payload 改动，不触碰引擎路径
- 如果 db boundary 收口导致验证结果异常，回滚 boundary 调用点，保留新模块文件以便后续继续迁移
- 如果 audit contract 影响核心产物 compare，立即回滚 audit 组装改动

## Open Questions

- `results/{run_id}` 旧读取路由是在下一条 retirement wave 直接删除，还是先改成内部只读 shim？
- `stock_names` 与 artifact stabilize 内部的 direct psycopg 查询，是否在本 wave 一次性全部迁入 db boundary，还是先覆盖公开 API 路由与 stabilize 必需查询？
