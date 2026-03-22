## 1. API Surface 最终收口

- [x] 1.1 删除桌面主路径对 `/api/backtest_v2/artifacts/read` 的剩余依赖并收敛到 `manifest/surface/section`；DoD：前端主路径中该接口命中为 0；验证：前端静态扫描 + 结果页 smoke；风险：遗漏隐藏调用点。
- [x] 1.2 清理 `backend/api/backtest_v2` 中仅为历史 artifact alias/fallback 存在的运行时读取分支；DoD：主读取链只认 canonical schema；验证：API 单测 + artifact 读取回归；风险：旧产物目录读取失败。
- [x] 1.3 将历史 alias/旧命名支持迁回离线迁移工具，移除运行时常驻兼容；DoD：`protocol.py/data_impl.py/artifacts_impl.py` 主路径不再承担旧 alias 归一化；验证：静态搜索 + 查询服务回归；风险：误删仍被主路径使用的字段。
- [x] 1.4 继续拆分 `runner_impl.py`、`artifacts_impl.py`、`configs_impl.py`、`semantic_config_compiler.py` 的混合职责；DoD：大文件边界更单一且无行为变化；验证：对应单测 + compileall；风险：请求编译或结果拼装漂移。

## 2. 结果区单 Owner 与前端运行真相

- [x] 2.1 彻底删除结果区 fallback/Fallback only 的残余逻辑、样式和桥接死代码；DoD：生产结果区只保留 Vue workbench；验证：静态搜索 + 前端 harness；风险：误删仍被主路径引用的桥接代码。
- [x] 2.2 将 `backtest_v2.js`、`desktop-load-controls.js`、`desktop-save-controls.js`、`desktop-config-controls.js` 从 `input_source_meta` 进一步收口到 `manifest/runtime snapshot` 主真相；DoD：来源提示和加载语义以 runtime source 为主；验证：前端状态测试；风险：配置来源提示退化。
- [x] 2.3 抽离前端 config draft core，使 `ui-controls.js` 只保留控件联动和展示提示；DoD：表单到 runtime request 的主编译链进入独立模块；验证：前端 harness + config round-trip 测试；风险：请求 payload 漂移。
- [x] 2.4 清理 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 中剩余乱码文案和历史命名；DoD：用户可见文本与核心状态命名统一为干净语义；验证：node --check + 文案搜索；风险：误改测试预期。

## 3. 研究入口硬收口

- [x] 3.1 将剩余顶层 `study-definition` 脚本批量迁入 `.study.yaml + generated thin script`；DoD：每个迁移专题都有 study 与 generated 入口；验证：study migration tests；风险：stored payload 不一致。
- [x] 3.2 删除已过时且已等价迁移完成的顶层 `run_*_research.py`；DoD：顶层研究入口数量显著下降且 inventory 同步；验证：governance 测试；风险：误删仍有唯一价值的研究入口。
- [x] 3.3 对明显过时、无主线价值的 research/diagnostic/sweep 顶层脚本直接删除，不保留兼容 wrapper；DoD：inventory 中不再保留无价值入口；验证：inventory 覆盖测试；风险：删除后缺少审计记录。
- [x] 3.4 更新 `backend/scripts/README.md`、`inventory.json` 与 `backend/research/thin_script.py` 约束，明确 generated-only 主路径；DoD：文档、清单、模板一致；验证：governance 测试 + 生成脚本检查；风险：清单与真实文件漂移。

## 4. backend/core 热点拆分

- [x] 4.1 为 `breakout_signal_provider.py`、`strict_runtime_impl.py` 建立职责拆分清单，优先标出纯 helper、类型、格式化和可抽离段；DoD：形成文件级拆分边界；验证：代码审阅 + 调用链核对；风险：误把行为逻辑当 helper。
- [x] 4.2 逐步抽离 `portfolio_builder.py`、`market_snapshot_service.py`、`regime_router_signal_provider.py`、`multi_alpha_signal_provider.py` 的纯函数和共享 helper；DoD：热点文件体量下降且依赖方向更清晰；验证：单测 + compileall；风险：行为细节被顺手改动。
- [x] 4.3 在 core 热点拆分过程中禁止修改执行时点和成交语义，并对每个切片复核 `baseline_V10.1` 快照；DoD：perf/counters 保持一致；验证：固定 regression snapshot；风险：把结构重排引入为语义漂移。

## 5. 运行时 canonical 与离线迁移收尾

- [x] 5.1 继续运行并收尾 canonical artifact migration，确保主路径不再依赖历史 trades/counter/shell label；DoD：历史 alias 仅存在于迁移工具；验证：migration audit + query regression；风险：历史目录局部漏迁。
- [x] 5.2 删除只为兼容旧 shell label、旧 counter 字段存在的运行时代码；DoD：运行时主路径只保留 canonical 命名；验证：静态搜索 + regression snapshot；风险：漏删造成双语义并存。

## 6. 回归与最终收口

- [x] 6.1 对前端、API、study、core 热点各自补齐最小边界测试，覆盖本 change 删除兼容层后的新真相；DoD：新增测试能阻止旧载体回流；验证：pytest + frontend harness；风险：测试只验证文本不验证行为。
- [x] 6.2 每个阶段结束后复核 `baseline_V10.1 -> exp_20260314_144548534_7db9` 的 `total_return/max_drawdown/cagr/sharpe/calmar/trades/turnover/orders/closed_trades`；DoD：前后完全一致；验证：experiment_query_service regression snapshot；风险：环境噪音被误判成漂移。
- [x] 6.3 清理完成后重新盘点“仍需整理文件清单”，确认本 change 触达的主干债已清零或明确只剩高风险行为热点；DoD：形成最终清单与剩余风险结论；验证：静态扫描 + 代码审阅；风险：把普通大文件误判为历史遗留。
