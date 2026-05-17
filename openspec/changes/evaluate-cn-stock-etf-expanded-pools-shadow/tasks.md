## 1. 实验合同

- [x] 1.1 新增联合影子 study 定义。DoD：`research/studies/cn_stock_etf/cn_stock_etf_expanded_pool_shadow_v1.study.yaml` 可被 `study_run --dry-run` 加载，包含 5 个 variant 与 3 个窗口；验证：dry-run 输出 15 个计划项；风险：variant 命名与 ETF-only study 不一致导致结果不可追溯。
- [x] 1.2 固定联合实验控制组。DoD：variant 同时包含 `CURRENT_FORMAL_COMBO_REPLAY`、`FORMAL_POOL_ROTATION_CONTROL`、`REALWORLD_POOL_V1`、`INDUSTRY_THEME_POOL_V2`、`STYLE_SMART_BETA_POOL_V2`；验证：单测或 dry-run 断言 variant 清单；风险：只和 ETF-only formal control 比，漏掉当前正式组合锚点。

## 2. Runner 实现

- [x] 2.1 新增 `cn_stock_etf_expanded_pool_shadow` runner。DoD：runner 从 `CN_STOCK_ETF_FORMAL_V1` 读取 workbench config，按窗口生成 combo request；验证：helper 单测覆盖请求结构；风险：手写配置偏离正式组合模板。
- [x] 2.2 正确替换 ETF sleeve 且保持 stock sleeve 不变。DoD：扩池 variant 只替换 ETF component `compile_input.semantic_config` 与 source metadata；验证：单测比较 stock component source 与 template 一致；风险：误改股票 alpha 或组合权重。
- [x] 2.3 三窗口边界写入两个子组件。DoD：top-level、stock component、ETF component 的 `universe.start/end` 都等于 study window；验证：单测覆盖 `1217`；风险：窗口标签生效但子组件仍跑全周期。
- [x] 2.4 移除旧 execution contract 覆盖风险。DoD：组合请求不携带模板旧 `unified_runtime.execution_contract`；验证：单测断言旧 ETF runtime symbols 不存在；风险：扩池配置被旧 runtime config 静默覆盖。

## 3. 结果与验证

- [x] 3.1 写出每个运行项的联合结果行。DoD：结果包含 combo exp_id、stock exp_id、ETF exp_id、window、variant、ETF 池版本、关键 perf、research_only；验证：runner 结果 schema 单测；风险：结果无法追踪到组件实验。
- [x] 3.2 运行相关单测。DoD：新增 runner 单测和 study runner 相关测试通过；验证：`python -m pytest` 指定测试文件；风险：只跑实盘 smoke 漏掉合同漂移。
- [x] 3.3 运行 OpenSpec 校验。DoD：`openspec validate --changes evaluate-cn-stock-etf-expanded-pools-shadow` 通过；验证：CLI exit 0；风险：spec 格式不满足归档要求。

## 4. Docker 三窗口实验与结论

- [x] 4.1 在 Docker 内确认数据最新边界。DoD：记录 A 股与 ETF 数据共同可用结束日；验证：容器内查询数据库 max trade_date；风险：窗口结束日超过某一侧数据覆盖。
- [x] 4.2 在 Docker 内跑 smoke。DoD：至少 `1226` + `STYLE_SMART_BETA_POOL_V2` 成功，产出 combo 与 component exp_id；验证：`study_run` exit 0；风险：runner 请求无法通过 runtime 编译。
- [ ] 4.3 在 Docker 内跑三窗口全量矩阵。DoD：15 个运行项都有 exp_id、结果目录和关键指标；验证：study 输出 summary 与产物存在；风险：运行耗时或单个 ETF 池数据覆盖失败。
- [ ] 4.4 输出联合口径结论。DoD：对比 ETF-only 与 stock+ETF 联合结果，说明胜出原因、标的名称/行业属性、防守仓与 beta 仓后续区分建议；验证：报告包含收益、回撤、Sharpe、交易/暴露和风险解释；风险：只看收益不看稳健性。
