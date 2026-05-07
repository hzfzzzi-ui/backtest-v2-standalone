## 1. 账户运营域对象收口
- [x] 1.1 定义 `accounts / holdings_snapshots / cash_ledger / sync_logs` 的正式边界。  
  DoD: proposal/design/spec 与数据库文档一致；验证: OpenSpec validate 通过；风险: 正式对象边界不清导致再次混层
- [x] 1.2 明确 `cash_ledger` 与 `sync_logs` 属于同一账户运营子域，但保持两个正式对象。  
  DoD: spec 覆盖两类对象；验证: scenario 区分现金变动与同步日志；风险: 日志与账本混写

## 2. sim_account 正式真相迁移
- [x] 2.1 将 `sim-account-holdings-sync` 改为正式写入/读取持仓快照，而不是长期依赖文件产物。  
  DoD: spec 明确持仓快照为正式对象；验证: capability scenario 覆盖快照写入；风险: 旧同步服务继续只写文件
- [x] 2.2 将 `sim-account-auto-sync` 改为正式写入账户运营日志与现金账本。  
  DoD: spec 明确同步日志/现金账本路径；验证: capability scenario 覆盖同步结束状态；风险: 现金更新与同步结果脱钩

## 3. reconcile 收口
- [x] 3.1 将 `position-aware-reconcile-run` 收口为派生分析结果，只保留摘要/引用进入数据库。  
  DoD: spec 明确 reconcile 非底层真相；验证: capability scenario 覆盖摘要落库；风险: 上层继续依赖完整 payload 当真相
- [x] 3.2 定义 `outputs/ops/sim_account/*` 的迁移期 compat 与退出条件。  
  DoD: 设计中明确过渡期角色；验证: design 与 specs 一致；风险: 文件路径继续扩张

## 4. 验证与回退
- [x] 4.1 补回归与回退说明，形成 apply-ready 任务基线。  
  DoD: proposal/design/tasks/specs 完整；验证: OpenSpec status 4/4；风险: 实现阶段缺少迁移顺序
