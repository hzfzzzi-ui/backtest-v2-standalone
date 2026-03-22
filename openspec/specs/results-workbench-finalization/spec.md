# results-workbench-finalization Specification

## Purpose
定义结果工作台成为结果区唯一渲染 owner 后的最终契约。
## Requirements
### Requirement: 结果工作台必须成为结果区唯一渲染 owner
当 Vue 结果工作台挂载成功后，系统 MUST 仅由结果工作台渲染结果概览、KPI、主图、个股排名、9 阶段漏斗、交易明细和 AI Markdown 报告。legacy 脚本 SHALL NOT 继续直接写入可见结果区 DOM。

#### Scenario: Vue 挂载成功
- **WHEN** 页面加载并成功挂载结果工作台
- **THEN** 可见结果区 SHALL 仅由 Vue 渲染
- **THEN** 页面 SHALL NOT 再保留可见的 fallback 结果容器

#### Scenario: Vue 挂载失败
- **WHEN** 结果工作台挂载失败
- **THEN** 系统 MUST 记录失败状态到前端状态或诊断输出
- **THEN** 页面 SHALL NOT 回退到独立 legacy 结果区

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

### Requirement: 生产主路径必须移除 fallback 结果 DOM
系统 MUST 从生产主路径中移除 fallback 结果 DOM。桌面结果区在正常运行下 SHALL 只保留 Vue results workbench 作为唯一可见结果渲染 owner。

#### Scenario: 桌面页正常加载
- **WHEN** 用户正常打开桌面研究页并加载实验结果
- **THEN** 结果区 MUST 仅由 Vue results workbench 渲染
- **THEN** 页面 SHALL NOT 再保留可见的 fallback 结果容器

#### Scenario: 旧脚本尝试更新结果 DOM
- **WHEN** `backtest_v2.js`、`artifacts.js` 或其他旧脚本参与结果刷新
- **THEN** 这些脚本 MUST 只更新 snapshot 或调用 workbench 桥接层
- **THEN** 它们 SHALL NOT 直接写入旧结果面 DOM

### Requirement: desktop-research-page 必须成为唯一结果协调层
系统 MUST 让 `desktop-research-page` 成为桌面结果加载、snapshot 组装与 workbench 推送的唯一协调层。其他旧控制器 SHALL NOT 绕过该层直接接管结果渲染流程。

#### Scenario: 加载某个实验 surface
- **WHEN** 桌面页请求某个实验的主 surface 或 section
- **THEN** `desktop-research-page` MUST 负责组装 `ResultsWorkbenchSnapshot`
- **THEN** Vue workbench MUST 仅消费该 snapshot

### Requirement: 结果工作台必须区分未单独计数与真实零值
结果工作台在渲染交易漏斗时 MUST 保留后端提供的 `available` 与 `null` 语义。对于 `available=false` 或阶段计数为 `null` 的阶段，结果工作台 MUST 显示“未单独计数”或等价状态，并 MUST NOT 将该阶段格式化为数值 `0`。对于 `available=true` 且阶段计数真实为 `0` 的阶段，结果工作台 MUST 按真实零值显示。

#### Scenario: 渲染 unavailable 阶段
- **WHEN** 结果工作台收到某个漏斗阶段 `available=false`，或 `input_count / output_count / filtered_count` 为 `null`
- **THEN** 该阶段 SHALL 显示 unavailable 或未单独计数状态
- **THEN** 该阶段的数值位 SHALL NOT 渲染为 `0`

#### Scenario: 渲染真实零值阶段
- **WHEN** 结果工作台收到某个漏斗阶段 `available=true` 且计数值真实为 `0`
- **THEN** 该阶段 SHALL 直接显示 `0`
- **THEN** 该阶段 SHALL NOT 被标记为 unavailable 或 missing

#### Scenario: view model 不得吞掉空值语义
- **WHEN** 结果工作台 helper 或 view model 构造漏斗面板数据
- **THEN** helper SHALL 保留 `available=false` 与 `null` 语义到最终渲染层
- **THEN** helper SHALL NOT 通过数值格式化或 `Number()` 收敛把空值阶段改写成 `0`

