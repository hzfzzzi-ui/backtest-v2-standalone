## Context

当前已经完成 ETF-only 的 realworld、industry/theme、style/smart-beta 三轮扩池实验，但这些实验没有和 A 股个股 sleeve 联合运行。正式组合锚点是 `CN_STOCK_ETF_FORMAL_V1`，其 unified runtime 通过 `component_source_contract` 指定 stock 与 ETF 两个组件来源，同时配置中还保留了已编译的 `execution_contract` runtime 快照。

本轮目标不是迁移正式 ETF 池，而是验证：扩展 ETF 池放回 `stock + ETF` 组合后，是否仍然改善组合层风险收益，并且改善是否来自 ETF 池而不是股票 sleeve、窗口错配或旧 execution_contract 覆盖。

## Goals / Non-Goals

**Goals:**

- 通过 `study_run` 增加一个 research-only 联合影子实验入口。
- 固定 stock sleeve 的正式语义配置，只对 ETF sleeve 使用指定 ETF-only study 的配置。
- 三窗口运行时同时改写 stock 与 ETF 子组件的 `universe.start/end`，确保窗口口径真实生效。
- 输出可复核的矩阵结果：window、variant、combo exp_id、stock exp_id、ETF exp_id、ETF 池、关键指标和相对基线差异。

**Non-Goals:**

- 不修改 `CN_STOCK_ETF_FORMAL_V1`、`baseline_V10.1` 或任何正式 baseline 注册。
- 不修改股票 alpha、ETF 排序规则、信号时点、成交时点、账户层和防守层定义。
- 不把 ETF 扩池候选升级为正式 ETF 池。
- 不在前端或 `outputs/` 中沉淀新的业务逻辑。

## Decisions

### Decision 1: 用 `study_run` 自定义 runner，而不是临时脚本

实现一个 `runner_mode=cn_stock_etf_expanded_pool_shadow` 的 study runner。这样研究入口仍受 `.study.yaml`、study plan、study conclusion 和 dual output 约束，避免出现一个不可审计的临时脚本。

替代方案是写独立 Python 脚本直接循环运行实验。该方案执行快，但会绕过现有 study governance，不符合当前研发秩序。

### Decision 2: 以 `CN_STOCK_ETF_FORMAL_V1` 的 workbench config 作为组合模板

runner 从 `outputs/baselines/CN_STOCK_ETF_FORMAL_V1/config.json` 读取 `workbench_config`，保留 unified combo 结构、组件权重和 stock 组件来源，只替换 ETF 组件的 compile input。

替代方案是手写全量组合配置。该方案容易漏掉正式组合已有的 metadata 和组件合同字段，不利于回溯。

### Decision 3: 移除模板中的旧 `execution_contract` 快照

模板的 `execution_contract` 内含已编译的 ETF runtime config。如果不移除，运行时会优先使用旧 runtime config，导致 ETF 扩池配置被覆盖。本轮 shadow runner 在生成请求时删除 `unified_runtime.execution_contract`，让运行时从当前 `component_source_contract.components.*.compile_input.semantic_config` 编译子组件。

替代方案是同步重写 execution_contract 中的 runtime config。该方案需要额外调用编译器生成 runtime 快照，复杂度更高，且会把本轮焦点从“ETF 池联合验证”扩展到 execution contract 再编译链路。

### Decision 4: 控制组分两层

结果同时保留两种控制语义：

- `CURRENT_FORMAL_COMBO_REPLAY`：当前正式组合模板重跑，用于观察当前正式组合锚点在最新窗口下的表现。
- `FORMAL_POOL_ROTATION_CONTROL`：使用与扩池 ETF-only 实验相同的 standalone rotation contract，但 ETF 池仍为 formal pool，用于隔离“扩池”相对“合同差异”的贡献。

扩池组包括 `REALWORLD_POOL_V1`、`INDUSTRY_THEME_POOL_V2`、`STYLE_SMART_BETA_POOL_V2`。

## Risks / Trade-offs

- [Risk] 三窗口标签与子组件实际窗口不一致 -> runner 必须同时 patch stock 与 ETF 组件的 `universe.start/end`，并在单测中断言。
- [Risk] 旧 `execution_contract` 覆盖扩池 ETF 配置 -> runner 必须删除旧 execution contract，并在单测中断言不存在旧 ETF runtime symbols。
- [Risk] 组合改善来自 contract 差异而非扩池 -> 同时运行 formal rotation control 与扩池组，结论中分开讨论。
- [Risk] 15 组联合运行耗时较长 -> 支持 `--variant` / `--window` 过滤，先 smoke 后全量跑。
- [Risk] 输出被误解为正式迁移 -> study、run meta 和报告均标注 research-only，且不写 baseline 注册。

## Migration Plan

新增 study、runner 和单测后，先 dry-run 验证矩阵，再在 Docker 内跑一个窗口的 smoke，最后跑三窗口全量。回退方式是删除新增 study、runner 分支、runner 文件和测试；正式 baseline 与正式 ETF 池没有迁移动作。

## Open Questions

- A 股个股数据是否覆盖到 `2026-05-08` 需要在运行前用容器内数据库确认；若不足，以 A 股与 ETF 两侧共同可用的最新日期作为本轮窗口终点，并在报告中显式记录。
