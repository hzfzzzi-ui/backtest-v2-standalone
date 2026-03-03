## Why

回测系统即将进入正式实验阶段。当前引擎输出的 CSV/JSON 产物侧重于"结果展示"（NAV 曲线、交易列表、KPI），但缺少一份面向**正确性验证**的结构化审计文件。用户计划在每次实验后将产物交给外部 AI（Gemini）审查回测是否真实可信，需要一份机器可读的 audit.json，包含逐日恒等式检查、价格合理性分析、成本审计和可疑模式标记。

## What Changes

- 在 VECTOR 引擎仿真循环中嵌入 **5 个审计检查点**（CP1–CP5），逐日记录现金守恒、持仓守恒、NAV 一致性、T+1 执行验证、成交价格合理性
- 循环结束后汇总为 **audit_summary**，包含全部交易日的恒等式通过率、价格分布统计、成本审计、信号→成交可追溯性计数
- 自动检测并标记 **可疑模式**（涨跌停成交、现金负值、持仓超限、NAV 出现 NaN、策略僵死等）
- 在 stabilize 阶段将审计结果写入实验目录的 **audit.json**，并更新 manifest.json 的 artifacts 字段
- audit.json 采用"**汇总 + 异常日**"策略：顶层为 summary，仅对检查失败或成交异常的交易日保留完整 day_audit 记录

## Capabilities

### New Capabilities
- `backtest-audit`: 回测审计检查点系统——在引擎仿真循环中埋入恒等式检查、价格/成本合理性验证、可疑模式检测，输出 audit.json 供外部 AI 审核

### Modified Capabilities
（无——audit.json 作为新增产物附加到现有 stabilize 流程，不改变已有产物的 schema）

## Impact

- **引擎核心**：`portfolio_simulator_strict.py` — 两条仿真路径（SMA / generic signals）均需插入检查点逻辑
- **产物层**：`backtest_v2_artifacts.py` — stabilize 阶段新增 audit.json 写入
- **配置/模型**：无变更（审计检查点为内部诊断，不需要用户配置）
- **前端**：无变更（audit.json 面向外部 AI 消费，不在 UI 展示）
- **性能**：检查点仅做加减法和比较，对热循环的额外开销可忽略
