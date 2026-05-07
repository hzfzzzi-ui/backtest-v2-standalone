## Context

当前主线已经在文档、runtime 和结果消费层把 `execution_contract` 收口成唯一正式执行真相，但结构层仍残留 4 个核心问题：

1. 组件 `runtime_config` 不是纯单腿合同，而是“系统总合同 + 当前作用域”的裁剪版。
2. `compiled_plan.json` 同时承载编译计划、来源装配和可执行输入，历史上事实上承担了执行真相职责。
3. `run_meta.json` 仍是运行事实、结果摘要、上下文和镜像副本的混合容器。
4. baseline 目录把“身份绑定”和“配置快照”混在一起，`config.json` 容易被误读成正式定义。

这些问题已经直接影响调试、审计和回滚：用户很难判断结果变化到底来自执行合同、来源装配、还是展示层镜像。当前 change 的目标不是调整研究逻辑，也不是改变策略收益，而是继续收紧系统边界，让执行链、结果层和 provenance 真正分层。

## Goals / Non-Goals

**Goals:**

- 让组件级 `runtime_config` 成为纯组件执行合同，不再携带兄弟腿 governed 子树或无关 schema 映射。
- 让 `compiled_plan` 只保留编译/装配快照角色，正式执行真相始终由 `execution_contract` 承担。
- 让 `run_meta` 收口为运行事实索引，只保留 runtime facts、`execution_contract_ref`、依赖索引和 provenance。
- 让 baseline 目录分成“身份绑定”“配置快照”“列表缓存”三类对象，并明确执行合同定位链。
- 保持旧实验、旧 baseline、旧前端在兼容窗口内可读，但不允许旧结构继续越权为执行真相。

**Non-Goals:**

- 不改变 A 股 stock sleeve、ETF sleeve 或 unified combo 的研究逻辑与收益口径。
- 不重构整个 governed 配置系统；本次只在 compile/runtime 投影层做纯化。
- 不要求一次性删除所有旧字段；允许在兼容窗口保留 legacy 别名，但必须明确降级。
- 不把 `component_source_contract` 从编辑/装配层完全删除；它仍可服务于 anchor 恢复和 provenance 说明。

## Decisions

### 决策 1：组件执行合同通过“纯投影”生成，不直接复用全量 governed 总合同

当前 stock / ETF 组件 `runtime_config` 的脏点来自同一个源头：compile 先构造整套 `governed_a_share` 总合同，再靠 `asset_scope` 与 `enabled` 标志切换腿。这样虽然能跑，但组件合同不纯，调试时会看到 stock leg 携带 ETF 子树，反之亦然。

本次决定在 compile 层增加“组件级 pure projection”：

- compiler 仍可使用全量 governed 总合同作为内部归一化输入
- 但进入 `execution_contract.components[*].runtime_config` 之前，必须做 scope-pure 投影
- 纯投影只保留当前组件实际执行需要的字段、子树和 schema 映射

这样可以把变更面限制在 compile/runtime 投影层，而不立即打穿所有使用 `build_governed_a_share_contract()` 的调用点。

**备选方案：**
- 直接改 `cn_a_governed_mainline.py` 的默认合同，让它按 scope 原地删子树  
  不选，因为影响面过大，会波及单腿与非 combo 调用方。

### 决策 2：`compiled_plan` 与 `execution_contract` 分层，`compiled_plan` 不再承担执行真相

历史上旧实验没有 `execution_contract.json`，导致 `compiled_plan.json` 被消费层当成“事实上的执行真相容器”。这会让 compile snapshot 与 execution truth 混写。

本次决定：

- 新实验必须落独立 `execution_contract.json`
- `compiled_plan.json` 只保留编译快照、组件解析结果、assembly trace
- 运行时和前端结果层不得再从 `compiled_plan` 推断执行真相
- 旧实验允许通过兼容逻辑从 `compiled_plan` 还原执行合同，但这属于 legacy 只读路径

**备选方案：**
- 继续允许 `compiled_plan` 和 `execution_contract` 双写、双读  
  不选，因为这会保留双真相风险。

### 决策 3：`run_meta` 收口为“运行事实索引”，执行全文镜像降级为兼容副本

`run_meta` 当前混合了执行镜像、组合摘要、上下文对象和 provenance，用户很难判断哪个字段才是权威位置。

本次决定：

- `run_meta` 主体长期只保留：
  - `status / timings / counters / data / code / asset_context / report_consistency`
  - `execution_contract_ref`
  - `dependencies`
  - `provenance`
- `combo_context / combo_result / research_combo / combo_runtime` 中的合同镜像与来源字段迁出或降级
- `run_meta.execution_contract` 仅作为兼容镜像暂留，逐步迁出

**备选方案：**
- 完全保留 `run_meta` 现状，仅靠前端和文档约束消费者  
  不选，因为结构脏点仍会在新模块里继续扩散。

### 决策 4：baseline 对象拆成身份对象、配置快照和列表缓存三层

当前 baseline 目录里：

- `baseline.json` 已基本适合作为身份绑定对象
- `config.json` 实际是装配/编辑快照，却容易被误读成正式定义
- `index.json` 是列表缓存，但没有被严格限定职责

本次决定：

- `baseline.json` 继续保留为唯一正式 baseline 身份对象
- baseline 必须显式绑定 `linked_exp_id` 与 `execution_contract_ref`
- 新增 `baseline_config_snapshot.json` 作为装配/编辑快照
- `config.json` 在兼容窗口内保留为 legacy alias，内容与 `baseline_config_snapshot.json` 同步
- `index.json` 只做列表缓存与摘要，不参与真相推导

**备选方案：**
- 继续沿用 `config.json` 命名，只靠文档说明降级  
  不选，因为文件名本身就会误导使用者。

### 决策 5：前端结果层只消费执行真相与 provenance，编辑层单独保留装配读取

结果工作台现在已经优先读 `execution_contract`，但 helper 里还保留了多层旧 contract 兜底。另一方面，编辑器仍需要 `component_source_contract` 来恢复 anchor 派生配置。

本次决定分层处理：

- results workbench / runtime-surface 只允许解释：
  - `execution_contract` 或 `execution_contract_ref`
  - `provenance`
  - view-model (`comboTruth`) 仅作展示
- config-workspace / config-draft 仍可读取 `component_source_contract`，但必须明确这是编辑恢复路径

## Risks / Trade-offs

- **[风险] 纯化组件 `runtime_config` 可能改变 compile 输出外观** → **缓解**：先在 unified combo 组件投影层落地，不直接修改全局 governed 默认合同，并用金标测试锁住字段集合。
- **[风险] `compiled_plan` 拆责会影响旧工具链** → **缓解**：保留 legacy 只读兼容窗口，新消费方强制切到 `execution_contract`，旧消费方只读 fallback。
- **[风险] `run_meta` 镜像迁出会影响前端或诊断脚本** → **缓解**：先把迁出字段转为 provenance 或专门摘要对象，补前端/测试同步修改，再逐步删旧镜像。
- **[风险] baseline 文件改名会影响现有入口** → **缓解**：先新增 `baseline_config_snapshot.json`，保留 `config.json` 兼容别名，再在后续 change 中移除。
- **[风险] 工作区本来就很脏，本轮容易和其它正在进行的改动冲突** → **缓解**：本次实现只碰 runtime/产物/基线/前端主路径的最小文件集，不回退用户已有改动。

## Migration Plan

1. 先补 spec、golden 和 guardrails，锁定组件纯合同、`compiled_plan` 边界、`run_meta` 精简和 baseline 三层对象。
2. 在 compile 层增加组件 pure projection，让新生成的 `execution_contract.components[*].runtime_config` 变纯。
3. 调整 unified combo runtime 和 artifact finalize，只把纯执行合同和 provenance 写到正式位置。
4. 新增 baseline snapshot 文件并补 `execution_contract_ref`，保留 `config.json` 兼容别名。
5. 收前端结果消费层，减少旧 contract 兜底，保留编辑器恢复路径。
6. 用 unit/integration/front-end tests 与 execution contract goldens 做回归，确认没有改动研究口径。

## Open Questions

- `run_meta.execution_contract` 的全文镜像是否在本次就迁出，还是保留一个兼容窗口？当前建议保留兼容窗口，避免一次性打穿历史读者。
- `compiled_plan` 的 assembly trace 是内嵌在 `compiled_plan.json` 里，还是拆成单独 artifact？当前建议先内嵌并瘦身，避免一次性新增太多文件。
- baseline 目录是否立刻切换前端读取到 `baseline_config_snapshot.json`？当前建议先双写，再在下一轮移除 `config.json` 读取。
