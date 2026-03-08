## 1. 结构壳与构建链
- [x] 1.1 为结果工作台新增 Vue 3 + Vite 最小结构与构建脚本。
  DoD：仓库出现结果工作台源码目录、构建入口与构建命令。
  验证：`npm run build:results-workbench` 能生成结果工作台 bundle。
  风险：静态资源路径与现有 `index.html` 引用不一致。
- [x] 1.2 在 `frontend/index.html` 中增加结果工作台挂载点与构建产物引用，并保留 legacy fallback。
  DoD：页面可同时加载 legacy 运行区与结果工作台挂载点。
  验证：浏览器打开页面无脚本报错，Vue 壳可挂载。
  风险：挂载点位置破坏 100% 缩放布局。

## 2. 结果桥接层
- [x] 2.1 抽取单一结果桥接层，统一承接 `baseline / experiment / manifest / artifacts / 视图状态`。
  DoD：legacy JS 不再在多个模块里重复维护结果快照。
  验证：加载 `baseline_V1` 与 `exp_20260308_021045840_cde0` 时桥接状态可观测。
  风险：bridge 与 legacy state 双写导致状态漂移。
- [x] 2.2 让 legacy 加载/运行流程只向桥接层推送标准快照，不再直接更新已迁移结果区 DOM。
  DoD：结果区刷新由桥接层驱动。
  验证：运行、加载 baseline、加载 experiment 后结果区都能更新。
  风险：遗留代码仍偷偷写结果区 DOM。

## 3. Vue 结果工作台迁移
- [x] 3.1 用 Vue 组件接管结果概览、个股排名、9 阶段漏斗、详细交易明细、AI Markdown 报告。
  DoD：这些区域在 Vue 壳中渲染且口径与现状一致。
  验证：baseline_V1 页面 smoke 可看到完整结果区。
  风险：漏斗、报告、表格字段在迁移中丢失。
- [x] 3.2 用 Vue 包装接管主图表区，但继续复用 `charts.js` 原语。
  DoD：图表通过 Vue 生命周期挂载/销毁，个股绝对收盘价、相对倍率、基准对比展示不漂移。
  验证：baseline_V1 下图表模式切换、symbol 切换可用。
  风险：图表实例生命周期中的 resize/sync 回归。

## 4. 验证与 legacy 收口
- [ ] 4.1 以 `baseline_V1` 和 `exp_20260308_021045840_cde0` 完成 100% 缩放人工 smoke 验证。
  DoD：结果区 accordion、滚动条、KPI、漏斗、交易表、AI Markdown 报告全部可用。
  验证：人工 smoke 清单与截图对照。
  风险：布局在不同窗口尺寸下再次挤压。
- [ ] 4.2 清理被 Vue 壳接管区域中的 legacy 结果区 DOM 写入与死代码。
  DoD：legacy 代码不再直接渲染已迁移结果面板。
  验证：搜索结果区关键节点只剩桥接层与 Vue 壳引用。
  风险：误删尚未迁移的 fallback 逻辑。
