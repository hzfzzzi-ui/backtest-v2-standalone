## 1. API 边界与契约

- [ ] 1.1 建立 `backend/api/backtest_v2/*` 和 `backend/api/mobile/*` 正式目录并让旧 `endpoints/*` 只做 path 兼容 shim；DoD: 新目录承担正式实现入口；验证: 旧 path 和新实现返回语义一致；风险: shim 期间出现双真相。
- [ ] 1.2 落地 `ExperimentManifest`、主 `ExperimentSurface`、懒加载子面和 `ExecutionPreview` 契约；DoD: 主面与子面职责清晰；验证: API 合约测试覆盖主面/子面字段；风险: 字段拆分导致前端读错语义。
- [ ] 1.3 统一历史实验列表为 `manifest + 少量 perf 摘要`；DoD: 列表接口不再内联大 surface；验证: 历史列表与加载弹窗测试通过；风险: 摘要字段过少导致前端比较信息不足。

## 2. 应用层服务收口

- [ ] 2.1 将实验运行、artifact 读取、实验查询和对比逻辑收口到 services；DoD: route 文件只做协议翻译；验证: route 级集成测试通过；风险: 迁移过程中出现行为漂移。
- [ ] 2.2 固化 `experiment_summary_service` 和 `baseline_report_service` 的接口契约；DoD: service 接口可被后续脚本面消费；验证: 单元测试能构造 summary/baseline 写入对象；风险: 提前耦合到脚本实现细节。

## 3. 前端页面壳与状态切片

- [ ] 3.1 将桌面研究页最少拆为 `configDraft`、`runSession`、`activeExperiment`、`viewState` 四个状态切片；DoD: 单一巨型 state 被拆开；验证: 页面基本交互与切换实验流程正常；风险: 旧 DOM 仍读旧状态字段。
- [ ] 3.2 将 [backtest_v2.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/backtest_v2.js)、[ui-controls.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/ui-controls.js)、[artifacts.js](/C:/Users/hzfzzzi/openclaw/backtest_V2_standalone/frontend/assets/js/artifacts.js) 降级为 page shell / feature / presenter；DoD: 页面控制器不再承载完整业务逻辑；验证: 相关前端 smoke 测试和手工流程通过；风险: 迁移期兼容代码继续膨胀。
- [ ] 3.3 让移动只读面改为消费基于统一 surface 派生的移动摘要对象；DoD: 移动端不再直接依赖桌面重型字段；验证: 移动接口与页面渲染测试通过；风险: 摘要派生丢失关键结果语义。

## 4. 结果工作台桥接

- [ ] 4.1 将 `ResultsWorkbenchSnapshot` 固化为桌面结果工作台唯一输入真相；DoD: workbench 不再直接 fetch 后端；验证: workbench 组件集成测试通过；风险: snapshot 字段不完整导致组件自行回查。
- [ ] 4.2 实现 `fetch -> build snapshot -> push snapshot` 单向桥接与懒加载子面合流；DoD: `nav / symbol_stats / stage_funnel` 由 page shell 按需加载并汇入 snapshot；验证: 桌面端结果页完整渲染通过；风险: 子面懒加载时序导致 UI 闪烁或状态错乱。

## 5. 验证与文档

- [ ] 5.1 验证 `baseline_V10` 在相同输入下结果不漂移；DoD: 关键输出与现状一致；验证: 回归测试或金样本对比通过；风险: 契约重构顺带改变结果口径。
- [ ] 5.2 更新 OpenSpec/README/开发说明，写明新 API 边界、主 surface/子面规则和 snapshot 约束；DoD: 文档可指导后续 change 不再绕回巨型入口；验证: 文档审阅通过；风险: 文档落后于实现。
