## ADDED Requirements

### Requirement: fallback 结果容器必须降级为显式受控的诊断路径
系统 MUST 将 fallback 结果容器降级为显式受控的诊断路径。正常生产路径下，Vue results workbench MUST 成为唯一可见结果 owner；fallback 容器默认 MUST 处于 `hidden + inert` 状态。

#### Scenario: Vue workbench 正常挂载
- **WHEN** 页面成功挂载 Vue results workbench
- **THEN** fallback 结果容器 MUST 保持隐藏且不可交互
- **THEN** `backtest_v2.js`、`artifacts.js` 等旧脚本 SHALL NOT 继续向 fallback 容器写入可见结果 DOM

#### Scenario: 显式进入诊断模式
- **WHEN** 用户或开发者通过显式诊断开关进入 fallback 模式，或 workbench 挂载失败且状态中心已记录失败原因
- **THEN** 系统 MAY 启用 fallback 容器
- **THEN** fallback 激活原因 MUST 可被状态中心或诊断输出观察
