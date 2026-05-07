## 1. 合同与入口修复

- [x] 1.1 扩展 unified combo execution contract 写出组件级 `execution_overrides`；DoD：新合同含 stock/ETF 两个组件的 overrides；验证：单元测试读取合同字段；风险：旧合同缺字段需兼容。
- [x] 1.2 调整 unified combo runtime 子腿请求组装，应用组件级 `execution_overrides` 到 request body；DoD：`runtime_config_json` 子腿也能启用 final_score/MF 排名；验证：个股子腿 counters 不再全为 0；风险：body 字段与 runtime_config 冲突时必须以合同 overrides 为准。
- [x] 1.3 增加 baseline execution contract 解析 helper，按 `baseline.json.execution_contract_ref` 读取合同；DoD：可从 `A_STOCK_ETF_V1` 定位 linked experiment 下的 `execution_contract.json`；验证：helper 单元测试；风险：历史 baseline 缺 ref 只能兼容读取，不得伪装正式复跑。

## 2. ETF 编译口径修复

- [x] 2.1 将 ETF phase1 promotion 改为条件化；DoD：显式 R1 standalone ETF 配置不被改写；验证：编译后 `source_entry_type` 和 universe 保持 R1；风险：缺省 phase1 路径不能被破坏。
- [x] 2.2 补充 ETF 编译回归测试；DoD：R1 与 phase1 两类输入分别覆盖；验证：pytest 指定测试通过；风险：测试不能依赖不稳定产物。

## 3. 验证与复跑

- [x] 3.1 运行相关单元测试；DoD：合同生成、runtime 子腿请求、ETF 编译测试通过；验证：pytest 输出；风险：仓库存在大量历史脏改，测试范围必须收窄。
- [x] 3.2 重跑 `A_STOCK_ETF_V1`；DoD：新 run 的 stock component 排名 counters 恢复，ETF component 口径保持 R1；验证：比较 perf、run_meta、execution_contract；风险：如果历史基线合同本身缺少 overrides，需要先重建/迁移合同再复跑。
