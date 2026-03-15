# results-workbench-finalization Specification

## Purpose
定义结果工作台成为结果区唯一渲染 owner 后的最终契约。
## Requirements
### Requirement: 结果工作台必须成为结果区唯一渲染 owner
当 Vue 结果工作台挂载成功后，系统 MUST 仅由结果工作台渲染结果概览、KPI、主图、个股排名、9 阶段漏斗、交易明细和 AI Markdown 报告。legacy 脚本 SHALL NOT 继续直接写入可见结果区 DOM。

#### Scenario: Vue 挂载成功
- **WHEN** 页面加载并成功挂载结果工作台
- **THEN** 可见结果区 SHALL 仅由 Vue 渲染
- **THEN** legacy 结果区容器 SHALL 被设置为 `hidden`
- **THEN** legacy 结果区容器 SHALL 被设置为 `inert`

#### Scenario: Vue 挂载失败
- **WHEN** 结果工作台挂载失败
- **THEN** 系统 MAY 回退到 legacy 结果区
- **THEN** fallback 行为 SHALL 被显式记录到前端状态或诊断输出

### Requirement: 结果工作台不得依赖 legacy 全局 helper
结果工作台用于构造漏斗、退出原因、Markdown 报告和结果格式化的逻辑 MUST 通过前端模块 import 获取。结果工作台 SHALL NOT 依赖 `window._finalBuildStageRows`、`window.renderUnifiedStageFunnel`、`window.reasonByPrefix`、`window.buildAgentMarkdownReport` 这类 legacy 全局 helper。

#### Scenario: 漏斗 view model 构造
- **WHEN** 结果工作台渲染 9 阶段漏斗
- **THEN** 数据准备 SHALL 来自纯模块函数
- **THEN** 不得从 `window.*` 读取漏斗构造函数

#### Scenario: Markdown 报告构造
- **WHEN** 结果工作台渲染 AI Markdown 报告
- **THEN** 报告拼装 SHALL 来自纯模块函数
- **THEN** 不得从 `window.*` 读取报告构造函数

### Requirement: 结果区展开状态必须由单一状态源控制
结果区 accordion、dock 和展开/收起状态 MUST 由单一状态源控制。多个原生脚本 SHALL NOT 并行修改同一批结果区节点的 `open`、`wb-open` 或 `hidden` 状态。

#### Scenario: 点击结果面板标题展开
- **WHEN** 用户点击个股排名、9 阶段漏斗或交易明细的标题
- **THEN** 展开状态 SHALL 由单一状态源更新
- **THEN** 不得出现“命中点击但内容不展开”的情况

#### Scenario: 从 dock 切换到结果面板
- **WHEN** 用户通过 dock 切换到某一个结果面板
- **THEN** 系统 SHALL 打开对应面板
- **THEN** 不得与点击逻辑产生冲突或双写

### Requirement: baseline 页面在 100% 缩放下必须稳定
使用 `baseline_V1` 加载结果工作台时，系统 MUST 在浏览器 100% 缩放下完整显示结果区，不得出现横向溢出、卡片错位、折叠内容被压扁或主图遮挡。

#### Scenario: baseline 默认加载
- **WHEN** 页面以 `baseline_V1` 作为默认加载对象打开
- **THEN** 结果区 SHALL 正常显示概览、KPI、主图和折叠面板
- **THEN** 页面 SHALL NOT 发生持续向右滚动

#### Scenario: baseline 展开面板
- **WHEN** 用户在 100% 缩放下展开个股排名、9 阶段漏斗或交易明细
- **THEN** 面板内容 SHALL 完整显示
- **THEN** 下面的结果区块 SHALL 被正常推开而不是覆盖

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

