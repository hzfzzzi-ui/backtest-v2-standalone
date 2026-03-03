## Context

当前协议相关逻辑分散在 `backend/api/endpoints/backtest_v2.py`、`backend/api/endpoints/backtest_v2_artifacts.py` 与前端 `frontend/assets/js/backtest_v2.js`。历史演进中出现了文件名与字段名并存（例如 `reason_codes.csv` 与 `reason_code_counts.csv`，以及 `run_meta.counters` 的短名与 `_count` 命名），导致文档、测试、实现三方口径不一致。

本次变更目标是先建立协议单一事实源（canonical contract），再通过兼容窗口平滑迁移，避免一次性破坏历史结果读取。

约束条件：
- 必须保持前端历史实验可读。
- 必须遵守架构宪法中的“向后兼容新增，不做无声破坏”。
- 不调整策略逻辑和回测引擎业务行为，仅收敛协议与读写路径。

## Goals / Non-Goals

**Goals:**
- 将 `reason_codes.csv` 设为标准原因码聚合文件名。
- 将 `run_meta.counters` 标准化为短名字段：`raw_signal/blocked/orders/skipped/closed_trades`。
- 将 `symbol_performance.csv` 设为必出产物（允许空文件）。
- 缺失产物时统一行为：写空文件，并在 `run_meta.missing_fields` 记录缺失来源。
- 提供两版本兼容窗口：读取侧兼容旧文件名和旧字段名，写入侧仅输出标准口径。
- 对齐文档与测试，使“文档-实现-测试”同口径。

**Non-Goals:**
- 不重构策略引擎、撮合逻辑、风险逻辑。
- 不调整前端 UI 交互与图表样式。
- 不在本变更中引入新的产物类型（仅固化现有口径）。

## Decisions

### 决策 1：采用“标准写 + 兼容读”迁移策略
- 选择：写入路径只输出 canonical 协议；读取路径兼容 legacy。
- 原因：可快速停止新漂移，同时保证历史实验可读。
- 备选方案：
  - 直接只认新协议：迁移成本低但会破坏历史结果读取。
  - 长期双写双读：兼容最好但会长期保留复杂度和歧义。

### 决策 2：文件名 canonical 固定为 `reason_codes.csv`
- 选择：`reason_codes.csv` 作为唯一标准。
- 原因：当前前端已直接消费该命名，且命名更短、可读性更好。
- 兼容：读取时继续接受 `reason_code_counts.csv`（两版本）。

### 决策 3：`run_meta.counters` canonical 固定为短名
- 选择：`raw_signal/blocked/orders/skipped/closed_trades`。
- 原因：与 `funnel.csv` 和前端统计口径一致，减少字段映射成本。
- 兼容：读取时接受 `_count` 旧名回退（两版本）。

### 决策 4：`symbol_performance.csv` 升级为必出产物
- 选择：无交易或数据缺失也必须生成空文件并登记 artifacts。
- 原因：前端面板不再需要猜测是否存在该能力，渲染路径稳定。
- 备选方案：保持可选产物，会继续增加前端分支判断复杂度。

### 决策 5：缺失产物统一降级策略
- 选择：缺失即写空文件 + `run_meta.missing_fields` 标注。
- 原因：既不阻断流程，也保留可观测性与诊断能力。
- 约束：`missing_fields` 必须使用稳定键名，避免“自由文本”失控。

### 决策 6：契约实现收口到共享协议模块（实现阶段）
- 选择：抽出协议常量与映射（文件名、字段名、legacy alias）到单一模块，路由与 artifacts 复用。
- 原因：避免同一协议在多个文件硬编码再次漂移。

## Risks / Trade-offs

- [风险] 兼容窗口期间出现“旧读新写”隐性分支增多  
  -> 缓解：集中 legacy alias 映射；在代码中禁止散落硬编码。

- [风险] 测试仍按旧口径断言导致 CI 噪音  
  -> 缓解：拆分“主契约测试（仅 canonical）”与“兼容测试（legacy）”。

- [风险] 文档更新滞后于实现导致团队误用  
  -> 缓解：将文档更新纳入同一 change 的必做任务，并在评审中强制核对。

- [风险] 两版本兼容到期后遗留历史读取路径未清理  
  -> 缓解：在 `run_meta` 或日志中输出 legacy 命中计数，作为清理触发信号。

## Migration Plan

1. 文档先行：更新 `SCHEMA_rows` 与 `SCHEMA_run_meta` 的 canonical 定义。  
2. 写路径收敛：统一后端写出 `reason_codes.csv` 与短名 counters。  
3. 读路径兼容：实现 legacy alias 回退读取（文件名 + 字段名）。  
4. 测试分层：主契约仅断言 canonical，兼容测试断言 legacy 可读。  
5. 观测增强：记录 legacy 命中次数，评估两版本后移除窗口。  
6. 兼容淘汰：到期后移除 legacy 读取并更新文档版本说明。

## Open Questions

- 两版本的“版本单位”以发布版本号还是以迭代批次计数，需要在发布流程中进一步定义。
- legacy 命中统计放在日志还是 `run_meta` 字段，需结合现有观测面板决定。
