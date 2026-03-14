## 1. 研究脚本

- [x] 1.1 新增 `backend/scripts/run_breakout_buffer_research.py`；DoD：脚本以 V9.1 baseline 为输入并生成 0.0/0.005/0.01 三组变体；验证：脚本可启动且打印实验计划；风险：误用错误 baseline exp_id
- [x] 1.2 在脚本中加入配置 diff 审计；DoD：仅允许 `strategy.params.breakout_entry_buffer_pct` 漂移；验证：非法改动会抛错；风险：嵌套字段路径比较不完整
- [x] 1.3 在脚本中写出结构化摘要；DoD：输出 `summary.json` 与 `summary.md`，包含 exp_id、results_dir 和核心绩效；验证：产物文件存在且字段完整；风险：结果字段名与实验返回值不一致

## 2. 执行与归档

- [x] 2.1 运行研究脚本完成三组实验；DoD：baseline、0.5% buffer、1.0% buffer 都产出实验目录；验证：每组都有 exp_id 和 results_dir；风险：本地数据库或缓存环境异常
- [x] 2.2 汇总审计与结果并更新任务状态；DoD：形成可直接汇报的结论，明确是否建议推进；验证：summary 与最终结论一致；风险：只看聚合指标导致误判
