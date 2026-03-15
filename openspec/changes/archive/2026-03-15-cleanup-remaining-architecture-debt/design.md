## Context

当前仓库已经完成三轮主边界重构，新的 `backend/api/backtest_v2/*`、`backend/api/mobile/*`、`ResultsWorkbenchSnapshot`、`study runner` 和执行总线都已经建立，`V10.1 -> exp_20260314_144548534_7db9` 也被固定为回归门。  
但代码审视后仍有 4 类历史残留会持续拉低架构优雅性：

1. 新 API 命名空间仍复用 `backend/api/endpoints/*` 中的 helper，导致新边界在物理结构上仍锚定旧目录。
2. 桌面结果区仍保留 Vue workbench 与 fallback DOM 双轨渲染，结果 owner 尚未在生产主路径上完全单一化。
3. `backend/scripts` 治理规则已经存在，但 study/CLI 迁移完成度很低，顶层脚本仍是事实上的第二套实验系统。
4. artifact / counter 的历史 alias 仍常驻运行时读取链路，阻碍 canonical schema 成为唯一真相。

本 change 的目标不是继续大改执行内核，而是在不改变 `V10.1` 结果和日线时点口径的前提下，把这些残留收成更干净的长期结构，降低后续接入多资产时的耦合。

## Goals / Non-Goals

**Goals:**

- 让新 API 边界不再依赖历史 `endpoints` helper 树，形成独立 shared helper surface。
- 让 Vue results workbench 成为生产路径的唯一结果区 owner，fallback DOM 只保留显式受控的开发/应急用途。
- 让高频研究脚本优先进入 `study definition + CLI + generated thin script` 主路径，压缩顶层活跃脚本面。
- 通过离线迁移清理历史 artifact alias，使运行时只读取 canonical artifact schema。
- 所有清理都必须以前后对照 `baseline_V10_1 -> exp_20260314_144548534_7db9` 为回归门，不允许结果漂移。

**Non-Goals:**

- 不重写 `breakout_signal_provider.py`、`strict_runtime_impl.py` 等高风险核心策略/执行逻辑。
- 不修改股票池、手续费、滑点、成交规则、基准或报表指标定义。
- 不把整套桌面前端迁移到新的框架或重写整个 workbench。
- 不在本 change 内完成所有历史研究脚本的全量迁移，只处理高频和主线脚本。

## Decisions

### 1. 共享 API helper 从 `endpoints` 目录剥离到 `backend/api/shared/*`

**Decision**  
将仍被新 API 目录复用的 helper 拆到独立的 `backend/api/shared/*`，例如路径工具、状态工具、job store、mobile access gate。新 `backtest_v2/*` 和 `mobile/*` 路由/impl 只允许依赖 shared 层，不再直接 import `backend/api/endpoints/*`。

**Why**  
继续让新 API 依赖 `endpoints` helper，会让“新边界只是目录名变化”这一问题长期存在。shared 层可以为多资产新 surface 提供中性宿主。

**Alternatives considered**

- 保留现状，只把 `endpoints` 当作 helper 容器：成本低，但历史目录会继续成为真实依赖根。
- 直接把 helper 复制进各新 impl：会制造重复实现，后续更难维护。

### 2. Vue workbench 成为唯一生产结果 owner，fallback DOM 降级为显式诊断路径

**Decision**  
正常生产路径下，结果区只能由 Vue results workbench 渲染。fallback DOM 默认保持 `hidden + inert`，仅在显式诊断模式或 workbench 挂载失败且状态中心记录后才允许启用。

**Why**  
双轨渲染会让任何新资产结果卡片都要同时实现 Vue 和 DOM 两套逻辑，直接阻碍扩展。

**Alternatives considered**

- 长期保留 fallback 作为常规运行兜底：看似稳妥，但会永久维持双 owner。
- 立刻完全删除 fallback：风险偏高，不利于排查极端挂载故障。

### 3. 脚本迁移按“高频优先、薄 wrapper 强制”推进

**Decision**  
对高频正式脚本和主线研究脚本，优先迁到 `study definition + CLI` 主路径；顶层脚本若继续保留，只允许作为薄 wrapper 或 archive。`backend/scripts/generated/run_<study_id>.py` 继续作为按需生成入口，而不是再生成大型脚本。

**Why**  
现阶段最不优雅的不是脚本多，而是“主线研究仍以顶层脚本为事实入口”。只有把高频脚本迁掉，治理规则才会真正生效。

**Alternatives considered**

- 一次性迁完所有历史脚本：范围过大，难以在一次清理中验证收益。
- 只保留 inventory 不继续迁：规则会变成纸面约束。

### 4. artifact alias 通过离线迁移退出运行时，而不是永久常驻读取链路

**Decision**  
保留独立的离线迁移器和迁移审计，但运行时查询链只认 canonical schema。历史 artifact 命名、counter alias、旧 shell label 通过离线更新产物解决，不再由线上读取逻辑长期兼容。

**Why**  
如果运行时长期保留 alias 归一化，canonical schema 永远不是真正唯一真相，也会让后续多资产扩展不断复制 alias 逻辑。

**Alternatives considered**

- 永久兼容读取历史 alias：实现简单，但技术债永久化。
- 完全不迁历史产物直接切断：风险过高，会破坏已有实验索引。

### 5. 清理顺序固定为“低风险结构 -> 中风险 UI -> 中风险脚本 -> 有状态迁移”

**Decision**  
任务按下列顺序推进：
1. API shared helper surface
2. workbench owner / frontend controller cleanup
3. 高频脚本迁移
4. artifact canonical migration
5. 最终回归与审计

**Why**  
这样可以先切掉纯结构性残留，再处理会影响工作流的 UI 和脚本，最后才做需要修改大量历史产物的 alias 退出。

## Risks / Trade-offs

- [Risk] API helper 抽离时出现隐式导入或循环依赖 → **Mitigation**：先建立 helper 映射表，再按单模块迁移并补 `boundary` 静态测试。
- [Risk] Vue workbench fallback 收紧后，极端浏览器环境失去可见结果区 → **Mitigation**：保留显式诊断开关，并要求状态中心记录 fallback 触发原因。
- [Risk] 脚本迁移不彻底，形成“双入口并存” → **Mitigation**：限定高频脚本批次，迁完即补 governance 测试，阻止新顶层活跃脚本回流。
- [Risk] artifact 离线迁移批量修改 `outputs` 后出现查询缺口 → **Mitigation**：先产出迁移审计报告，再分批迁移并用 `V10.1` 与代表性历史实验做读取回归。
- [Risk] 清理过程中误改执行口径 → **Mitigation**：所有阶段都必须以前后对照 `exp_20260314_144548534_7db9` 的 `perf/orders/trades/nav` 为门禁。

## Migration Plan

1. 盘点仍由新 API 目录直接引用的 `endpoints` helper，并迁入 `backend/api/shared/*`。
2. 将 `backtest_v2.js`、`artifacts.js` 中仍然会写入 fallback 结果 DOM 的生产路径收束到 Vue workbench；fallback 只保留诊断模式。
3. 选取高频研究脚本和高频正式脚本首批迁移到 `study/CLI/thin script`，并缩减顶层活跃脚本。
4. 实现 artifact 离线 canonical migration，先生成审计报告，再更新历史产物并删除运行时 alias 归一化。
5. 运行静态边界测试、script governance 测试、artifact 协议测试，以及 `V10.1` 回归验证。

**Rollback**

- API/helper 与前端 workbench owner 调整可通过单模块回滚。
- 脚本迁移保留 archive 与 thin wrapper，可逐文件回退。
- artifact canonical migration 需要先保留迁移前索引或 git 快照；若读取回归失败，先恢复迁移器和 alias 逻辑，再回退受影响产物批次。

## Open Questions

- 是否为 fallback DOM 保留显式 URL/debug flag，还是仅允许通过开发模式启用。
- 高频研究脚本首批迁移是否只覆盖 V10 主线，还是同时纳入当前仍在活跃使用的非 V10 专题。
