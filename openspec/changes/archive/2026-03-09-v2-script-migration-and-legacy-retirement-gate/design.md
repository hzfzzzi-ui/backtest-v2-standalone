## Context

截至 `v2-surface-convergence-and-retirement-gate`，系统已经把公开产品表面收敛到：

`config_json -> experiment_id -> manifest -> declared artifacts`

且锁定基线 `exp_20260308_021045840_cde0` 的核心结果仍然稳定。  
但实际代码库里还有三类残余调用面没有收口：

- 直接调用公开 HTTP 运行接口、但仍然依赖旧配置字段或旧结果结构的脚本，例如 `run_alpha_v1.py`
- 直接 import endpoint 私有实现的内部工具，例如 `baseline_regression_check.py`
- 直接依赖 `report.html`、`results_dir`、原始文件名布局的诊断/重跑工具，例如 `report_consistency_check.py` 与 `run_clean_data_standard_reruns.py`

如果现在直接进入大规模删旧代码，最大的风险不是回测计算口径漂移，而是这些脚本和内部工具被误伤，导致无法继续做基线复跑、历史报告核验和候选 clean rerun。

## Goals / Non-Goals

**Goals:**
- 形成一份完整的调用者矩阵，区分 `public caller`、`internal helper caller`、`frozen legacy script`
- 设计并收敛 internal helper 边界，让内部脚本不再直接依赖 endpoint 私有函数或公开旧表面
- 明确哪些 shim 可以保留为 internal-only，哪些模块可以进入第一批删除候选
- 继续以 `exp_20260308_021045840_cde0` 为结果不变门禁，保证这轮收口不碰脏结果

**Non-Goals:**
- 本 change 不修改回测引擎数学逻辑，不修改成交时点，不修改 9-stage 计算口径
- 本 change 不在这一轮直接删除所有旧代码；先做迁移边界与退役门槛，再进入真正删除
- 本 change 不扩大公开 `config_json` 契约去承载仅旧脚本使用的历史排序/成本字段
- 本 change 不改变实验目录中核心产物文件名与 manifest 主消费模式

## Decisions

### D1: 剩余调用者按三类治理，而不是一刀切

系统把剩余调用者固定分成三类：

- `public caller`
  - 面向前端、smoke、公开契约验证
  - 必须只使用公开 `config_json -> experiment_id -> manifest/artifact` 表面
- `internal helper caller`
  - 面向基线复跑、clean rerun、报告一致性等内部运维/研究工具
  - 可以使用 internal helper，但不能继续直接依赖 endpoint 私有实现
- `frozen legacy script`
  - 本轮无法迁移且不应继续扩张的脚本
  - 必须写入冻结文档，标明原因、替代路径和退役触发条件

选择理由：
- 这样可以把“产品真相”与“内部过渡工具”彻底拆开
- 也能避免为了照顾旧脚本而重新污染公开表面

备选方案：
- 要求所有脚本立刻改走公开 `config_json`
  - 拒绝，因为像 `run_alpha_v1.py` 仍依赖旧排序/成本参数，当前公开语义契约并不承载它们
- 继续允许脚本直接 import endpoint 私有实现
  - 拒绝，因为这会让 shim 边界一直模糊，后面无法安全删除旧壳

### D2: 建立显式 internal helper，而不是继续散落私有 import

本 change 设计一条显式的 internal helper 边界，用于承接内部工具的兼容需求。  
helper 的职责包括：

- 构建 internal experiment request
- 执行 internal rerun
- 读取 manifest 与声明产物
- 读取保存配置 provenance
- best-effort 报告导出/一致性检查辅助

选择理由：
- 内部脚本仍需要兼容能力，但不应继续耦合到 `_experiment_runner_api`、`_config_governance` 等私有 endpoint 实现
- 有了 helper，后续删旧代码时只需要保护一条边界，不需要保护每个脚本里的私有 import

备选方案：
- 继续让脚本分别 import `_experiment_runner_api`、`_candidate_presets`、`backtest_v2_artifacts`
  - 拒绝，因为这只是在保留旧耦合，不是收敛

### D3: 不为了旧脚本扩张公开 `config_json`

对像 `run_alpha_v1.py` 这类仍依赖旧排序/成本字段的脚本，本 change 的原则是：

- 能迁到 internal helper，就迁
- 不能迁，就冻结
- 不为它们回填公开旧字段
- 不为它们扩张公开语义 `config_json`

选择理由：
- 公开契约已经收敛，不能为了旧脚本再次打开多真相入口
- 内部脚本问题应该由 internal helper 或冻结清单承接，而不是回到产品表面

备选方案：
- 在 `config_json` 里新增只供旧脚本使用的 legacy 字段
  - 拒绝，因为这会把临时兼容需求固化进产品契约

### D4: 第一批删除候选必须基于证据，而不是“看起来没人用”

某个旧模块进入第一批删除候选前，至少必须满足：

1. 调用者矩阵显示无 live caller，或只剩已冻结脚本
2. 已存在清晰替代入口
3. 基线回归门禁继续通过
4. 如涉及报告/诊断工具，对应内部一致性检查仍可运行

选择理由：
- 这样可以把“删除”从主观判断变成证据驱动
- 也能避免误删仍被基线脚本或候选研究工具依赖的内部模块

备选方案：
- 先删再看 CI/运行时报错
  - 拒绝，因为这里很多工具依赖是运行时/研究流依赖，不一定会被普通测试覆盖

### D5: `report.html` 在内部工具里继续允许，但只能作为 optional artifact

`report_consistency_check.py` 这类脚本仍然可以检查 `report.html`，但其消费方式必须通过 manifest 或 internal helper 显式表达为 optional artifact，而不是把 `report.html` 重新提升回主消费面。

选择理由：
- 这和上一条 change 的公开表面收敛不冲突
- 也允许在真正删掉旧报告壳之前，继续保留必要的内部诊断能力

## Risks / Trade-offs

- [风险] internal helper 会在短期内形成新的过渡层  
  -> Mitigation：helper 必须冻结职责，不承载新产品逻辑，并附带退役门槛

- [风险] 某些旧脚本可能无法在本轮完整迁移  
  -> Mitigation：这类脚本必须进入冻结清单，不允许继续扩张

- [风险] 调用者矩阵如果漏统计，第一批删除候选会有误伤  
  -> Mitigation：用 import 检索、脚本入口审阅和基线门禁三重确认

- [风险] 公开表面和 internal helper 在短期内并存，心智成本会增加  
  -> Mitigation：文档里明确“公开真相”和“内部过渡面”的边界，并规定后续只允许删，不允许继续长新逻辑

## Migration Plan

1. 统计所有仍依赖旧字段、旧 import、旧 artifact 习惯的脚本与工具
2. 建立 internal helper 边界，并把基线复跑、clean rerun、报告一致性等工具迁到这条边界
3. 迁移或冻结仍直接调用公开旧表面的脚本
4. 形成第一批删除候选清单与删除前置条件
5. 执行基线门禁与内部诊断验证，确认只剩允许的 `report.html` 诊断漂移

回滚策略：
- 如果 helper 引入后导致工具链失效，先回滚 helper 接入，不回滚公开产品表面
- 如果脚本迁移导致基线门禁异常，先恢复该脚本到冻结状态，不触碰引擎与公开协议

## Open Questions

- `run_alpha_v1.py` 最终应迁到 internal helper，还是直接列入冻结并等待退役？
- `report_consistency_check.py` 后续是继续保留为 internal diagnostic tool，还是并入统一的 artifact audit helper？
- 当前未 archive 的历史 change spec，何时统一做主 spec sync 与归档？
