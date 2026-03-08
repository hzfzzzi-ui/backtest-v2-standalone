## ADDED Requirements

### Requirement: 锁定基线实验
系统 SHALL 将 `exp_20260308_021045840_cde0` 视为后端重构的锁定基线实验，并将该实验目录作为默认比较源。

#### Scenario: 读取锁定基线
- **WHEN** 任一后端重构验证任务启动基线比较
- **THEN** 系统 SHALL 默认读取 `outputs/experiments/exp_20260308_021045840_cde0`
- **THEN** 系统 SHALL 将该目录中的核心产物和配置快照视为比较基准

### Requirement: 保护产物集合必须分级比较
系统 SHALL 对锁定基线的保护产物集合执行分级比较，至少包含精确比较和语义比较两类。

#### Scenario: 精确比较核心回测产物
- **WHEN** 比较 `portfolio_daily.csv`、`portfolio_trades.csv`、`portfolio_candidates.csv`、`perf.json`
- **THEN** 系统 SHALL 以逐字段或逐行等价方式判定结果是否一致
- **THEN** 任一核心交易、NAV 或绩效字段漂移 SHALL 被标记为阻塞性差异

#### Scenario: 语义比较运行元信息
- **WHEN** 比较 `run_meta.json` 或 `manifest.json`
- **THEN** 系统 SHALL 忽略时间戳、临时路径、生成时间等允许漂移字段
- **THEN** 系统 SHALL 对 benchmark、日期范围、计数器、配置快照引用和核心产物映射执行语义一致性检查

### Requirement: 比较结论必须分为 PASS、WARN、FAIL
系统 SHALL 将基线比较结果归类为 `PASS`、`WARN` 或 `FAIL`，并以此控制后续重构阶段是否可以继续。

#### Scenario: 阻塞性差异
- **WHEN** 任一保护产物出现交易、NAV、绩效、核心计数器或配置真相漂移
- **THEN** 比较结论 SHALL 为 `FAIL`
- **THEN** 当前重构阶段 SHALL 被阻塞，不能继续删除旧代码或推进下一阶段

#### Scenario: 仅诊断性差异
- **WHEN** 差异仅来自时间戳、路径或允许漂移的诊断字段
- **THEN** 比较结论 SHALL 为 `WARN`
- **THEN** 系统 SHALL 要求在变更记录中显式说明差异来源

#### Scenario: 无差异
- **WHEN** 所有保护产物均通过比较
- **THEN** 比较结论 SHALL 为 `PASS`

### Requirement: 每次比较都必须写出机器可读报告
系统 SHALL 为每次基线比较写出 `baseline_compare.json`，用于机器校验和人工审阅。

#### Scenario: 比较报告生成
- **WHEN** 一次重构验证任务完成
- **THEN** 新实验目录 SHALL 包含 `baseline_compare.json`
- **THEN** 该文件 SHALL 包含 baseline_exp_id、candidate_exp_id、status、artifact_results、allowed_drift_fields、blocking_diffs 和 summary 字段

### Requirement: 基线门禁必须覆盖指定后端改动范围
系统 SHALL 要求所有触及配置解析、数据预加载、引擎编排或产物写盘的改动，在合并前执行基线比较。

#### Scenario: 触及重构关键目录
- **WHEN** 变更涉及 `backend/api/endpoints/`、`backend/core/tools/experiment_runner.py`、`backend/core/portfolio/`、`backend/core/engine_vector/`、`backend/core/data/` 或结果协议相关测试
- **THEN** 系统 SHALL 运行锁定基线比较
- **THEN** 在无 `PASS` 或已说明的 `WARN` 结果前，该变更 SHALL 不被视为可放行
