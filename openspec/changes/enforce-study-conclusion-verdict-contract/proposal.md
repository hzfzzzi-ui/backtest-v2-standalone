## Why

当前 study conclusion registry 会把 `study_gates` 产出的 `PASS/FAIL` 直接写成正式 `verdict`，导致“实验硬门槛通过”和“研究方向被接受/证伪”混用。最近 CSI1000 PIT 扩池 study 已经暴露该问题：A1 主窗口明显弱于 B0，却因为只满足 `min_trades` 被写成 `PASS`。

这会破坏研究留痕的可信度，也会让研究日志页面把 registry 里的 `PASS` 解读为正向结论。需要把文档中的标准合同变成可执行约束。

## What Changes

- 修改 study conclusion registry 合同：正式 `verdict` 只能表达研究结论，允许值收敛为 `confirmed`、`falsified`、`inconclusive`。
- 新增独立的 `gate_status` 字段承载运行硬门槛结果，例如 `PASS` / `FAIL` / `UNKNOWN`。
- `study_runner` 在写 registry 前必须把 hard gate 结果转换成正式 study verdict，不能直接把 `PASS/FAIL` 当作正式结论。
- `study_journal` 自动摘要必须基于正式 study verdict 判断正负向结论，同时继续展示 gate 状态。
- 增加单元测试覆盖：弱 hard gate 通过但相对 baseline 明显恶化时，registry 必须写 `falsified`，不能写 `PASS`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `study-conclusion-registry`: 正式结论 registry 必须区分 study verdict 和 hard gate status，并拒绝 `PASS/FAIL`  masquerade 成研究接受合同。
- `study-definition-runner`: study runner 完成 window/variant 后，必须写入符合正式 verdict 枚举的 conclusion record。

## Impact

- 影响代码：
  - `backend/research/study_conclusion_registry.py`
  - `backend/research/study_runner.py`
  - `backend/research/study_journal.py`
  - 相关 unit/integration tests
- 不影响项目：
  - 不修改交易执行口径
  - 不修改信号、排序、成交、退出、组合构建逻辑
  - 不修改已产出的 experiment artifact
- 风险：
  - 历史 registry 里已有 `PASS/FAIL` 记录，短期需要兼容读取；新写入记录必须使用正式 study verdict。
