## MODIFIED Requirements

### Requirement: 结果工作台必须成为结果区唯一渲染 owner
当 Vue 结果工作台挂载成功后，系统 MUST 仅由结果工作台渲染结果概览、KPI、主图、个股排名、阶段漏斗、交易明细和 AI Markdown 报告。旧 DOM 结果面和 fallback 容器 SHALL NOT 再作为生产路径保留。

#### Scenario: Vue 正常挂载
- **WHEN** 页面成功挂载结果工作台
- **THEN** 可见结果区 MUST 仅由 Vue workbench 渲染
- **THEN** 页面 SHALL NOT 再保留可见 fallback 结果容器

#### Scenario: 旧脚本尝试写入结果 DOM
- **WHEN** 旧控制器或旧 helper 试图直接更新结果区 DOM
- **THEN** 这些脚本 MUST 只更新 snapshot 或调用 workbench bridge
- **THEN** 它们 SHALL NOT 再直接拥有结果区 DOM

## REMOVED Requirements

### Requirement: Vue 挂载失败
**Reason**: 本 change 明确不再保留生产级 fallback 结果面；结果区单 owner 比保留双轨兜底更优先。
**Migration**: 页面如遇 Vue 挂载失败，记录错误状态并停止结果渲染；不得回退到独立 legacy/fallback 结果区。

