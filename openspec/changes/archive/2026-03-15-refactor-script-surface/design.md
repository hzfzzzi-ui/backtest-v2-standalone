## Context

当前仓库的脚本层已经不再是轻量辅助工具，而是第二套事实上的应用边界：

- `backend/scripts` 下当前有 70+ 个 Python 脚本，其中 `run_*` 研究脚本约 40+ 个。
- 多个研究脚本已经达到 700~1300 行，典型如：
  - [run_v10_residual_structure_s1_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_residual_structure_s1_research.py)
  - [run_v10_upstream_pullback_minimal_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_upstream_pullback_minimal_research.py)
  - [run_v10_quality_then_residual_s3_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_quality_then_residual_s3_research.py)
- 这些脚本普遍自己做：
  - `sys.path` 注入
  - `argparse`
  - baseline/preset/window/reference experiment 硬编码
  - config merge
  - result compare
  - report 输出

这带来两个直接问题：

1. AI 每次做实验时，很容易继续复制一个新的大脚本，而不是把逻辑沉回主系统。
2. 实验产物没有固定双轨输出，机器读结果、人读结论和 baseline 报告经常各自产生，难以追溯和复用。

用户已经明确提出两条未来约束：

1. 新实验必须遵循 `逻辑修改/新增 -> 接入引擎总线 -> 用统一模板生成脚本`。
2. 每次实验必须稳定产出：
   - 机器读 NAC/perf/audit/compare
   - 人读的简洁结论
   - 并自动并入 baseline 报告

## Goals

- 收编脚本面，把“正式命令”和“研究定义”从散脚本中抽出来。
- 建立统一 CLI 入口，避免继续长出新的大脚本。
- 建立 study definition + study runner 体系，替代绝大多数 `run_*_research.py`。
- 固化 `bus-first` 实验流程，保证 AI 新增逻辑先进入执行总线或 provider，再生成薄脚本。
- 固化 `dual-output` 产物流程，每次实验都产出机器读结果、人读结论和 baseline 更新。
- 保留历史脚本的可追溯性，但让它们退出主线。

## Non-Goals

- 本 change 不重写具体回测逻辑，那属于 `refactor-engine-execution-shell`。
- 本 change 不处理桌面/移动端页面结构，那属于 `refactor-runtime-boundaries`。
- 本 change 不要求一次性删除所有旧脚本。
- 本 change 不构建复杂工作流调度器，只建立统一命令面和研究定义面。

## Design Principles

### 原则 1：正式能力走 CLI，用例逻辑走 service

- 任何需要反复执行的正式能力，都必须有明确 CLI 子命令。
- CLI 只负责参数解析和输出格式。
- 真实业务逻辑必须在 service 或 study runner 中。

### 原则 2：研究配置声明式化

- 研究矩阵、窗口、baseline、对照组、通过门槛都必须进入 study definition。
- 不再允许这些内容埋在大型 Python 脚本里。

### 原则 3：薄脚本只是入口壳

- 统一模板生成的脚本只能：
  - 指定 `study_id`
  - 接收少量覆盖参数
  - 调统一 CLI/study runner
- 薄脚本禁止再次承载实验业务逻辑。

### 原则 4：实验结果必须双轨输出

- 每次实验都必须产出：
  - machine bundle
  - human bundle
  - baseline append
- 不允许只有 `perf.json` 没有结论。

### 原则 5：失败实验也必须进 baseline

- `FAIL` 不是本地临时结论，而是正式研究结论的一部分。
- 失败实验必须进入 baseline report，防止重复试错。

## Target Architecture

```text
AI / Researcher
  -> modify provider or bus module
  -> register in engine bus
  -> define study (.study.yaml)
  -> run via CLI / generated thin script
  -> experiment services execute
  -> outputs/
       experiments/<exp_id>/machine/*
       experiments/<exp_id>/human/*
       baselines/<baseline_id>/machine/*
       baselines/<baseline_id>/human/*
```

## Directory and File Responsibilities

目标目录：

```text
backend/
  cli/
    main.py
    commands/
      study_run.py
      experiment_compare.py
      data_refresh.py
      audit.py
    formatters/
      console.py
  research/
    study_definition.py
    study_loader.py
    study_runner.py
    study_gates.py
    study_reports.py
    studies/
      v10/
        *.study.yaml
backend/scripts/
  generated/
    run_<study_id>.py
  archive/
research/
  archive/
ops/
  contracts/
  reports/
  notes/
outputs/
  experiments/
  baselines/
```

### CLI Responsibilities

- `backend/cli/main.py`
  - 唯一正式命令入口。
- `backend/cli/commands/study_run.py`
  - study 定义执行入口。
  - 成为所有实验矩阵的唯一正式执行器。
- `backend/cli/commands/experiment_compare.py`
  - A/B compare、baseline compare。
- `backend/cli/commands/data_refresh.py`
  - 数据刷新。
- `backend/cli/commands/audit.py`
  - 审计和一致性检查。
- `backend/cli/formatters/console.py`
  - CLI 输出格式，不进入 service。

### Research Responsibilities

- `backend/research/study_definition.py`
  - study 领域模型。
- `backend/research/study_loader.py`
  - 从 `.study.yaml` 读取 study。
- `backend/research/study_runner.py`
  - 统一执行实验矩阵。
- `backend/research/study_gates.py`
  - 通过/失败门槛与最小证伪规则。
- `backend/research/study_reports.py`
  - 研究层的报告聚合。
- `backend/research/studies/**/*.study.yaml`
  - baseline、假设、变体、窗口、门槛、输出声明。

### Generated Scripts Responsibilities

- `backend/scripts/generated/run_<study_id>.py`
  - 统一薄脚本模板。
  - 只负责：
    - 指定 study
    - 转发少量参数
    - 调 `study_run`
  - 默认不为每个 study 自动生成，只有明确需要脚本入口时才生成。
- `backend/scripts/archive/`
  - 历史脚本归档，不再主线执行。

### Active Script Surface Policy

- 顶层 `backend/scripts/` 不再作为长期活跃主入口。
- 最终顶层只保留：
  - `generated/`
  - `archive/`
  - 少量内部 helper

## Script Classification Model

所有现有脚本都应被打上标签：

- `official-command`
  - 会反复使用，应该升格为 CLI 命令。
- `official-audit`
  - 审计类命令，也升格为 CLI。
- `study-definition`
  - 本质是在表达实验矩阵，应该转成 `.study.yaml`。
- `archived-study`
  - 保留历史可追溯性，但退出活跃层。
- `one-off-delete`
  - 临时一次性残留，先归档一段时间，再删除。
- `internal-helper`
  - 只能被 CLI 或 study runner 内部调用，不再作为用户入口。

### 示例迁移

- 升格为 CLI：
  - [baseline_regression_check.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/baseline_regression_check.py)
  - [update_pams_ohlcv_daily.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/update_pams_ohlcv_daily.py)
  - [refresh_csi1000_pit.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/refresh_csi1000_pit.py)
  - [report_consistency_check.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/report_consistency_check.py)
- 转为 study：
  - [run_v10_residual_structure_s1_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_residual_structure_s1_research.py)
  - [run_v10_quality_then_residual_s3_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_quality_then_residual_s3_research.py)
  - [run_v10_onset_ingress_minimal_s2_research.py](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/backend/scripts/run_v10_onset_ingress_minimal_s2_research.py)
- 归档：
  - 只对应单次专题结论、后续不会再滚动迭代的历史研究脚本。

## Bus-First Experiment Workflow

后续 AI 新实验必须遵循这条固定路径：

```text
1. 新增/修改逻辑
   -> provider or stage_pipeline built-in
2. 注册
   -> route_registry / registry / resolver
3. 暴露配置
   -> runtime config / study definition
4. 定义实验
   -> .study.yaml
5. 生成薄脚本
   -> backend/scripts/generated/run_<study_id>.py
6. 执行
   -> backend/cli study_run
7. 输出
   -> machine bundle + human bundle + baseline append
```

硬禁令：

- 不允许新建活跃的大型 `backend/scripts/run_xxx.py`。
- 不允许脚本自己 `sys.path` 注入。
- 不允许脚本自己拼完整 config merge 逻辑。
- 不允许脚本自己直接操作 engine 内部状态。
- 不允许绕过总线先写脚本、后补逻辑。

## Study Definition Contract

`.study.yaml` 至少强制以下字段：

- `study_id`
- `title`
- `baseline_id`
- `hypothesis`
- `change_scope`
- `variants`
- `windows`
- `hard_gates`
- `required_outputs`

说明：

- `change_scope`
  - 记录本轮只改什么。
- `variants`
  - baseline / primary variant / optional light perturbations。
- `windows`
  - 回测时段或子样本切片。
- `hard_gates`
  - 审计和稳健性最低门槛。
- `required_outputs`
  - 强制 machine/human/baseline 三类产物。

## Dual-Output Artifact Model

### Machine Bundle

目标目录：

```text
outputs/experiments/<exp_id>/machine/
  manifest.json
  nac.json
  perf.json
  audit.json
  compare.json
  surface.json
  config_snapshot.json
  run_meta.json
```

字段职责：

- `manifest.json`
  - 实验产物索引。
- `nac.json`
  - 机器读实验判断包。
- `perf.json`
  - 核心绩效指标。
- `audit.json`
  - 时间对齐、数据可得性、执行口径审计结果。
- `compare.json`
  - 对 baseline/champion 的比较。
- `surface.json`
  - 给桌面/移动/UI 共用的结果面。
- `config_snapshot.json`
  - 配置快照。
- `run_meta.json`
  - 运行元信息。

### NAC Contract

`NAC` 在这里定义为“机器读实验判断包”。当前不强行绑定缩写全称，但语义固定。

建议最小字段：

- `schema_version`
- `exp_id`
- `baseline_id`
- `study_id`
- `hypothesis`
- `change_scope`
- `audit`
- `robustness`
- `verdict`
- `next_action`

其中：

- `audit`
  - 是否通过时间对齐与口径审计。
- `robustness`
  - 是否通过阶段表现、轻微扰动和收益集中度检查。
- `verdict`
  - `PASS / FAIL / HOLD`
- `next_action`
  - `promote / iterate / archive / block`

### Human Bundle

目标目录：

```text
outputs/experiments/<exp_id>/human/
  conclusion.md
  summary.txt
```

要求：

- 结论优先。
- 尽量简洁。
- 必须明确：
  - 本轮只改什么
  - 审计是否通过
  - 稳健性是否通过
  - 是否进入下一轮

建议模板：

```text
[实验名]

结论：通过 / 不通过 / 待复核
原因：一句话说明

本轮只改了什么：
研究假设：
审计结论：
结果对比：
稳健性结论：
下一步：
```

## Baseline Report Integration

每次实验完成后，必须更新 baseline 资产：

```text
outputs/baselines/<baseline_id>/machine/
  experiment_ledger.jsonl
  latest_champion.json
  report_index.json

outputs/baselines/<baseline_id>/human/
  baseline_report.md
  baseline_digest.md
```

写入规则：

- 每次实验都追加 `experiment_ledger.jsonl`。
- 每次实验都追加 `baseline_report.md`。
- 只有 `PASS` 才允许申请更新 `latest_champion.json`。
- `FAIL` 也必须进入 baseline report。

## Migration Strategy

### 阶段 0：脚本盘点

- 对 `backend/scripts` 建立清单。
- 每个脚本都打分类标签和迁移目标。

### 阶段 1：建立统一 CLI 骨架

- 新建 `backend/cli/main.py`。
- 第一批正式子命令先锁：
  - `study_run`
  - `experiment_compare`
  - `data_refresh`
  - `audit`

### 阶段 2：建立 study runner

- 先转换 2~3 个最重的 V10 研究脚本为 `.study.yaml`。
- 让 `study_run` 能替代它们的主流程。

### 阶段 3：建立 dual-output services

- 由 `experiment_summary_service` 生成 machine/human 输出。
- 由 `baseline_report_service` 更新 baseline 资产。

### 阶段 4：启用 generated thin scripts

- 对仍希望“直接跑脚本”的工作方式，按需生成 `backend/scripts/generated/run_<study_id>.py`。
- 旧活跃大脚本转为 wrapper 或归档。

### 阶段 5：冻结旧脚本面

- 顶层 `backend/scripts` 不再接受新活跃研究脚本。
- 只允许：
  - `generated/`
  - `archive/`
  - 内部 helper

## Risks and Trade-offs

- 风险：旧脚本里存在隐式依赖，迁移到 study 后会暴露缺口。
  - 对策：先迁移最常跑、最值钱、最可复用的脚本，不做全量一刀切。
- 风险：NAC schema 早期容易频繁变动。
  - 对策：从第一版就声明 `schema_version`，允许后续演进。
- 风险：baseline 报告可能快速膨胀。
  - 对策：完整报告和 digest 分层，完整报告追加，digest 做摘要。
- 风险：使用者继续习惯性复制旧脚本。
  - 对策：加硬规则，新实验默认只给 study + thin script，不再给新大脚本模板。

## Acceptance Criteria

- 新实验不再以大型顶层 `run_*.py` 作为主要实现形式。
- `backend/cli/main.py` 成为正式命令入口。
- `study_run` 成为所有实验矩阵的唯一正式执行器。
- 每个实验都必须产出 machine bundle、human bundle 和 baseline append。
- generated thin scripts 行为受统一模板约束，不再重复实现业务逻辑。
- 高频正式脚本能力迁移到 CLI 命令面。
- 至少一批 V10 研究脚本成功转为 `.study.yaml + study_run`。
- AI 新增实验逻辑遵循 `bus-first` 路径，而不是绕过执行总线。

## Open Questions

- `nac.json` 是否需要进一步拆成 `audit_verdict` 和 `research_verdict` 两层。
- baseline 报告是按 baseline 单文件长期追加，还是定期滚动分卷。
- 旧脚本归档后是否保留原文件名，还是重命名为带日期/阶段的历史资产。
- generated thin script 是随 study 自动生成，还是只在用户明确要脚本入口时再生成。
