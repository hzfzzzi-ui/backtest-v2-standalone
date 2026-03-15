## 1. API 边界与契约
- [x] 1.1 建立 `backend/api/backtest_v2/*` 和 `backend/api/mobile/*` 正式目录，并让旧 `backend/api/endpoints/*` 只做 path 兼容 shim。
- [x] 1.2 落地 `ExperimentManifest`、主 `ExperimentSurface`、懒加载子面和 `ExecutionPreview` 契约。
- [x] 1.3 统一历史实验列表为 `manifest + 少量 perf 摘要`，不再内联重型 surface。

## 2. 应用层服务收口
- [x] 2.1 将实验运行、artifact 读取、实验查询和对比逻辑收口到 services，route 文件只做协议翻译。
- [x] 2.2 固化 `experiment_summary_service` 和 `baseline_report_service` 的接口契约，供后续脚本面消费。

## 3. 前端页面壳与状态切片
- [x] 3.1 将桌面研究页最少拆成 `configDraft`、`runSession`、`activeExperiment`、`viewState` 四个状态切片。
- [x] 3.2 将 `frontend/assets/js/backtest_v2.js`、`frontend/assets/js/ui-controls.js`、`frontend/assets/js/artifacts.js` 继续降级成 `page shell / feature / presenter`，直到页面控制器不再承载完整业务逻辑。
- [x] 3.3 让移动只读面改为消费基于统一 `ExperimentSurface` 派生的移动摘要对象。

## 4. 结果工作台桥接
- [x] 4.1 将 `ResultsWorkbenchSnapshot` 固化为桌面结果工作台唯一输入真相。
- [x] 4.2 实现 `fetch -> build snapshot -> push snapshot` 单向桥接与懒加载子面合流，使 `nav / symbol_stats / stage_funnel` 按需汇入 snapshot。

## 5. 验证与文档
- [x] 5.1 验证 `baseline_V10_1` 在相同输入下结果不漂移，并将 `exp_20260314_144548534_7db9` 作为当前回归基线。
- [x] 5.2 更新 OpenSpec / README / 开发说明，写明新 API 边界、主 surface / 子面规则、snapshot 约束和 V10.1 回归锚点。
