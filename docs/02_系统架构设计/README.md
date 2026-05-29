# 02 系统架构设计

本目录描述当前正式架构与边界，不再承载本轮重构过程叙事。历史演进材料仅保留在归档或变更记录中。

阅读顺序建议：

架构清理和边界判断优先阅读：[架构地图与边界规则.md](./架构地图与边界规则.md)

1. [全系统架构设计.md](./全系统架构设计.md)
2. [A股子系统架构设计.md](./A股子系统架构设计.md)
3. [前端与移动端/前端架构设计.md](./前端与移动端/前端架构设计.md)
4. [前端与移动端/前端接口边界.md](./前端与移动端/前端接口边界.md)
5. [前端与移动端/mobile_semi_auto_ops.md](./前端与移动端/mobile_semi_auto_ops.md)
6. [数据库/数据库架构设计.md](./数据库/数据库架构设计.md)
7. [数据库/市场数据访问边界.md](./数据库/市场数据访问边界.md)
8. [运行与基线/RUNBOOK_baseline_regression.md](./运行与基线/RUNBOOK_baseline_regression.md)
9. [运行与基线/Baseline 演进复盘报告.md](./运行与基线/Baseline 演进复盘报告.md)
10. [运行与基线/输出清理保留结论.md](./运行与基线/输出清理保留结论.md)

当前目录的主口径：
- 前端正式 owner 链已经收敛为 `host.js -> runtime-surface.js -> app-shell.js`
- unified combo 的正式运行真相是 `execution_contract`
- `component_source_contract` 只保留为来源装配与 provenance 说明
- 数据库兼容视图和 runtime contract 只在文档明确定义的边界内保留
- `outputs/` 只作为产物层，不作为源码主干

## 文档类型

| 路径 | 类型 | 说明 |
|---|---|---|
| `全系统架构设计.md`、`A股子系统架构设计.md`、`架构地图与边界规则.md` | 人读架构说明 | 当前架构主口径和边界判断 |
| `前端与移动端/前端*.md` | 人读架构说明 | 前端 owner、接口边界和展示层限制 |
| `前端与移动端/mobile_*.md`、`前端与移动端/sim_account_*.md` | 兼容/迁移说明 | 只描述过渡链路，不作为正式研究平台主路径 |
| `数据库/*_contract.md`、`数据库/v2_source_matrix.md`、`数据库/市场数据访问边界.md` | 合同/准机器文档 | 可被测试或实现引用的稳定数据合同 |
| `数据库/*.sql` | 机器执行材料 | 数据库 apply/rollback 脚本，必须配合 runbook 使用 |
| `数据库/*_runbook.md`、`运行与基线/RUNBOOK_*.md` | 运维 runbook | 执行步骤、验证方法和回退说明 |
| `运行与基线/*复盘*`、`输出清理保留结论.md` | 人读审计说明 | 复盘和治理结论，不替代 runtime 合同 |
