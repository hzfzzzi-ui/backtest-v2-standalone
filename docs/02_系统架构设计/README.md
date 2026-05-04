# 02 系统架构设计

本目录描述当前正式架构与边界，不再承载本轮重构过程叙事。历史演进材料仅保留在归档或变更记录中。

阅读顺序建议：
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
