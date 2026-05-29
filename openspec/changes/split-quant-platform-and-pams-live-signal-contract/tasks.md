## 1. 规格冻结与合同文件

- [ ] 1.1 与用户复核本 change 的 `proposal.md`、`design.md` 和 specs，确认双系统边界不再把 PAMS 作为研究策略来源；DoD：用户确认或批注完成；验证：OpenSpec 文件仍能通过 status；风险：边界未冻结前进入实现会继续产生双口径。
- [ ] 1.2 在研究平台新增 `daily_position_adjustment_package@1` schema 文档或 JSON Schema；DoD：字段、必填项、枚举、幂等键、失败状态、扩展策略写清；验证：schema fixture 可被校验；风险：schema 不稳定会导致 PAMS 入库和前端反复返工。
- [ ] 1.3 在 PAMS 新增对应入站合同文档，明确 PAMS 只接收 package 并做账户侧校验；DoD：PAMS 文档包含接口、数据库对象和禁止复算策略说明；验证：文档与研究平台 schema 字段一致；风险：两个仓库合同文本漂移。

## 2. 研究平台 live 发布侧

- [ ] 2.1 新增 live strategy registry 的最小配置和 loader；DoD：支持 `strategy_id`、`status`、`baseline_id`、`config_hash`、`execution_contract_hash`、`account_scopes`；验证：单测覆盖缺字段、非 `live_approved` 阻断；风险：未注册策略误推送。
- [ ] 2.2 从现有持仓感知 reconcile/action sheet 生成 package 草稿；DoD：package 包含 source、clock、scope、inputs、target_positions、action_sheet、risk_flags、validation；验证：fixture 输出与 schema 校验一致；风险：把 reconcile 误升格为账户真值。
- [ ] 2.3 实现发布前门禁校验；DoD：校验 registry 状态、baseline、config hash、execution contract hash、freshness、stale/drifted 状态；验证：失败用例返回明确 `failure_reason_codes`；风险：配置漂移后仍发布。
- [ ] 2.4 输出 no-op、blocked 和 audit copy；DoD：无调仓、风险阻断、数据缺失均有显式 package 或失败状态；验证：三类 fixture 均生成可解释结果；风险：静默跳过导致用户误判当天无信号。
- [ ] 2.5 增加研究平台单元测试和最小集成测试；DoD：覆盖 schema、门禁、幂等键、stale reconcile、blocked/no-op；验证：相关 pytest 通过；风险：未覆盖失败模式导致实盘日才暴露。

## 3. PAMS 入站与持久化

- [ ] 3.1 新增 PAMS 数据库迁移，保存 signal package 和 action；DoD：表包含 package header/source/clock/scope/status、action 明细、幂等唯一约束、审计时间戳；验证：迁移可重复执行；风险：缺少唯一约束导致重复通知。
- [ ] 3.2 新增 PAMS schema 校验模型；DoD：支持 `daily_position_adjustment_package@1` 校验、未知版本拒收、必填字段拒收；验证：有效/无效 fixture 单测通过；风险：PAMS 接收半结构化 payload 后难以审计。
- [ ] 3.3 新增 PAMS 入站 API；DoD：实现 `POST /api/live-signals/packages`、package 查询和 latest 查询；验证：重复提交返回已存在且不重复写 action；风险：接口语义不清导致研究平台重试产生副作用。
- [ ] 3.4 增加 PAMS 入站测试；DoD：覆盖成功入库、schema 失败、幂等重复、blocked/no-op package；验证：PAMS API 测试通过；风险：缺少测试会让通知和审批层依赖不稳定数据。

## 4. PAMS 通知、审批与交易生命周期

- [ ] 4.1 建立 PAMS package/action 的 app/web 查询服务；DoD：可按 `strategy_id`、`account_scope`、`signal_date` 查询最新调仓建议；验证：接口返回字段满足移动端展示所需来源和风险上下文；风险：前端再次从旧表拼装建议。
- [ ] 4.2 将 PAMS 通知来源切换到已校验 package/action；DoD：通知引用 `package_id` 和 `action_id`，包含策略来源、信号日期、动作摘要和风险标记；验证：通知测试或手动 API 调用可见；风险：旧 `pams_order_drafts` 与新 package 双重通知。
- [ ] 4.3 将用户审批映射到 PAMS 交易生命周期；DoD：批准/拒绝 action 会创建或更新 transaction，并保存 `source_package_id`、`source_action_id`、`strategy_id`、`strategy_run_id`、`config_hash`；验证：生命周期状态查询可追溯回 package；风险：审批状态分散在文件和 DB 两套真值。
- [ ] 4.4 增加审批和生命周期测试；DoD：覆盖 approve、reject、expire、blocked、partial fill/filled 回写的最小路径；验证：PAMS 相关测试通过；风险：执行状态无法回显给 app/web。

## 5. legacy 冻结与边界清理

- [ ] 5.1 盘点 PAMS 旧策略扫描、旧回测和复制版 `backtest_V2` 主入口；DoD：列出入口、调度任务、数据库表和前端依赖；验证：清单与 `rg` 搜索结果一致；风险：遗漏入口导致旧逻辑继续产出建议。
- [ ] 5.2 为 PAMS legacy 策略调度增加禁用开关；DoD：生产默认不从 legacy 策略扫描产生实盘通知；验证：scheduler 测试或 dry-run 显示任务被禁用；风险：直接删除可能破坏仍在使用的资产管理功能。
- [ ] 5.3 将研究平台 `mobile_ops` 和 approval ticket 文件链路标注为兼容/内部预览；DoD：文档、API 或代码注释明确长期真值在 PAMS；验证：相关测试仍通过；风险：过渡链路被误认为长期产品边界。

## 6. 端到端验收与回退

- [ ] 6.1 准备一组跨仓库 fixture package；DoD：包含 buy、sell、hold、blocked、no-op、invalid 六类样例；验证：研究平台生成和 PAMS 接收均能复用同一组 fixture；风险：两个系统各自维护样例导致合同漂移。
- [ ] 6.2 跑通本地端到端 dry-run；DoD：研究平台生成 package，PAMS 接收、入库、展示、通知、审批草稿全链路可观察；验证：命令、API 返回和数据库记录可复现；风险：单系统测试通过但跨系统失败。
- [ ] 6.3 编写回退说明；DoD：说明如何关闭 package 推送、如何保留审计文件、如何禁用通知切换、如何恢复旧资产管理展示；验证：回退步骤不要求修改 baseline 或研究口径；风险：上线失败后没有明确降级路径。
