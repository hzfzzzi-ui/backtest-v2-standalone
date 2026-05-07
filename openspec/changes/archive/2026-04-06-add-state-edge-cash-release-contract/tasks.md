## 1. 现金释放合同

- [x] 1.1 定义状态边缘触发条件，DoD：明确哪些状态切换会触发部分去风险；验证：spec 中有正式 edge 定义；风险：触发边界不清会导致日内行为漂移。
- [x] 1.2 定义释放现金的目标去向，DoD：现金释放与 defense/accumulation 的去向有正式说明；验证：design 中明确 release destination；风险：无目标去向会演变成无意义减仓。

## 2. runtime 与 explain

- [x] 2.1 接入状态边缘释放 explain，DoD：产物可解释是否触发 release、释放多少、为何未释放；验证：`run_meta` / reason codes 可追溯；风险：若解释层不足，将无法分辨是 edge 没触发还是执行失败。
- [x] 2.2 保持释放为部分去风险，DoD：本 change 不默认全清所有风险仓位；验证：contract 明确 bounded partial release；风险：若默认全清，会破坏账户层弱势累积能力。

## 3. 验收

- [ ] 3.1 用主基线和 ETF 弱势场景验证现金释放是否改善弱势可执行性，DoD：弱势现金约束问题减少且行为可解释；验证：改前改后 reason codes 与仓位行为对比；风险：若现金释放过猛，需回滚。
