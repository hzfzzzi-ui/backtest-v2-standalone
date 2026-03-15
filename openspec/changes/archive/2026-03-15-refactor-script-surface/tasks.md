## 1. CLI 与 study 骨架

- [x] 1.1 建立 `backend/cli/main.py` 和第一批正式子命令 `study_run / experiment_compare / data_refresh / audit`；DoD: 正式命令面可被调用；验证: CLI smoke test 通过；风险: 命令参数与现有脚本语义不一致。
- [x] 1.2 建立 `study_definition.py`、`study_loader.py`、`study_runner.py` 和必填字段校验； DoD: `.study.yaml` 能被统一装载和执行；验证: study 装载与缺字段测试通过；风险: study 契约过薄无法表达现有实验矩阵。

## 2. 双轨产物与 baseline 归档

- [x] 2.1 落地 machine bundle 八个强制文件和 `nac.json` 契约；DoD: 每次正式实验都能稳定产出 machine bundle；验证: 产物结构测试通过；风险: 机器读字段后续频繁漂移。
- [x] 2.2 落地 human bundle `conclusion.md` 和 `summary.txt`；DoD: 每次正式实验都有结论优先的人读输出；验证: 输出生成测试通过；风险: human 输出和 machine verdict 不一致。
- [x] 2.3 落地 baseline ledger/report/champion 更新规则；DoD: pass/fail 都会追加 ledger 和报告，只有 pass 才更新 champion；验证: baseline 写入测试通过；风险: fail 未入账导致重复试错。

## 3. 脚本分类与迁移

- [x] 3.1 建立现有脚本清单并打上 `official-command / official-audit / study-definition / archived-study / one-off-delete / internal-helper` 标签；DoD: 每个脚本都有迁移目标；验证: 清单审阅通过；风险: 分类不清导致迁移反复。
- [x] 3.2 将一批高频正式脚本迁入 CLI 命令面；DoD: 对应能力不再依赖顶层脚本；验证: 迁移后命令可重复执行；风险: 脚本中的隐式依赖未被抽出。
- [x] 3.3 将一批最重的 V10 研究脚本迁为 `.study.yaml + study_run`；DoD: 至少 2~3 个高价值专题可用新流程运行；验证: 研究结果与原流程一致；风险: 矩阵表达不完整。

## 4. 薄脚本与冻结旧脚本面

- [x] 4.1 提供按需生成的 `backend/scripts/generated/run_<study_id>.py` 模板；DoD: thin script 只做 study 入口转发；验证: 生成脚本 smoke test 通过；风险: 模板逐渐膨胀成业务实现。
- [x] 4.2 冻结顶层 `backend/scripts/` 活跃入口，仅保留 `generated/`、`archive/` 和内部 helper；DoD: 新实验不再新增顶层大型脚本；验证: 目录治理规则写入文档并执行；风险: 旧习惯继续绕过规则。

## 5. 验证与文档

- [x] 5.1 记录 `bus-first` 实验流程和“先接总线、再定义 study、最后生成脚本”的硬规则；DoD: AI/人工实验流程都有统一约束；验证: OpenSpec/README/流程文档更新完成；风险: 规则只写不执行。
- [x] 5.2 记录 dual-output 与 baseline 追加规则；DoD: 研究归档、machine/human 输出和 baseline 报告要求写入文档；验证: 文档审阅通过；风险: 实际实现偏离文档。


