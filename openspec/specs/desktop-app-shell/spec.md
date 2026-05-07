# desktop-app-shell Specification

## Purpose

定义桌面端单页宿主的正式边界，确保配置、运行、结果和状态中心在同一桌面宿主内组织，并由宿主负责统一布局与运行交互。

## Requirements

### Requirement: 桌面端必须以单页 desktop app 作为正式宿主

系统 MUST 提供单页 `desktop app` 作为桌面端正式宿主。

#### Scenario: 打开桌面主入口

- **WHEN** 用户打开桌面工作台
- **THEN** 系统进入统一桌面宿主
- **THEN** 顶部命令栏、配置工作区、运行编排、结果区和状态中心位于同一宿主边界内

### Requirement: 桌面端必须采用统一 app state

系统 MUST 使用统一页级 app state，并按配置、运行、当前实验和视图状态拆分切片。

#### Scenario: 运行结果写回宿主状态

- **WHEN** 一次运行完成并产出结果
- **THEN** 运行编排层写回统一 app state
- **THEN** 结果工作台只从统一状态读取结果

### Requirement: 宿主必须提供正式的运行取消交互

桌面宿主 MUST 在运行轮询期间提供取消交互，并通过正式 API 结束任务。

#### Scenario: 运行中显示取消

- **WHEN** 前端开始轮询运行中的 job
- **THEN** 宿主将运行按钮切换为“取消运行”
- **THEN** 宿主以显式状态提示当前任务仍在运行

#### Scenario: 用户取消运行

- **WHEN** 用户在轮询期间点击取消
- **THEN** 前端调用 `POST /api/backtest_v2/jobs/{job_id}/cancel`
- **THEN** 轮询结束并在状态区显示“已取消”

### Requirement: 宿主必须维护右侧主面板双 Tab 布局

桌面宿主 MUST 在右侧主面板提供 `[概览]` 与 `[分析]` 双 Tab 布局，作为结果与分析区的正式承载结构。

#### Scenario: 默认打开概览

- **WHEN** 页面加载或运行完成
- **THEN** 系统默认激活“概览” Tab

#### Scenario: 切换到分析

- **WHEN** 用户点击“分析”Tab
- **THEN** 系统展示分析页内容并隐藏概览页
- **THEN** 激活态 Tab 显示明确视觉高亮

### Requirement: 正式 desktop host 必须拥有共享状态 bootstrap owner 身份

系统 MUST 由 `desktop-shell/host.js` 创建并接管桌面共享状态，然后再分发页面级初始化。

#### Scenario: 打开桌面页面

- **WHEN** 用户打开桌面主页面
- **THEN** `desktop-shell/host.js` 先初始化共享状态
- **THEN** 页面主启动通过正式 host 分发

### Requirement: 正式 runtime surface 必须拥有共享 helper owner 身份

跨模块共享 helper、asset scope helper、runtime source helper 和结果桥接 helper MUST 由 `desktop-shell/runtime-surface.js` 提供。

#### Scenario: 工作台模块读取共享 helper

- **WHEN** workspace 或 orchestration 模块需要共享 helper
- **THEN** 它们从 `runtime-surface.js` 获取能力

### Requirement: 正式 app shell 必须拥有页面级 init / bridge owner 身份

页面级初始化、load hint、事件绑定与壳级 bridge wiring MUST 由 `desktop-shell/app-shell.js` 承担。

#### Scenario: 页面完成装载

- **WHEN** 桌面页面进入初始化阶段
- **THEN** `app-shell.js` 负责页面级 init 与 bridge wiring

### Requirement: 前端 harness 必须跟随正式装载链

前端 harness 与页面级测试 MUST 遵循与真实页面一致的装载顺序。

#### Scenario: harness 初始化桌面环境

- **WHEN** harness 启动桌面工作台上下文
- **THEN** 它先加载 `host.js`
- **THEN** 再加载 `runtime-surface.js` 与 `app-shell.js`
