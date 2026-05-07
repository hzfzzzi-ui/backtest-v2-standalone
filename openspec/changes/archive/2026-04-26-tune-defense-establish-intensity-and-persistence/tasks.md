## 1. 研究合同与参数入口

- [x] 1.1 在共享账户 transition policy 中增加 defense establish 研究变体字段，DoD：run_meta 可见 variant_id/edge_to_states/top_up 开关；验证：单次主回放检查 run_meta；风险：再次引入双语义
- [x] 1.2 在 ETF precompute 阶段消费这些字段，DoD：provider 上有稳定属性；验证：run_meta/formal_view 可见；风险：旧默认值被破坏

## 2. 行为实现与 A/B 实验

- [x] 2.1 把 defense establish 触发边界和 top-up 许可接入执行路径，DoD：不同变体能产生可区分订单行为；验证：orders.csv reason_code 对比；风险：误伤 sell-first
- [x] 2.2 运行最小 A/B 矩阵并记录结果，DoD：至少覆盖 current / RISK_OFF-only / RISK_OFF-only-no-topup；验证：主回放指标与状态行为对比；风险：变量过多导致归因变差

## 3. 结论与收口

- [x] 3.1 选择一个研究默认变体并固化代码，DoD：代码默认值与实验结论一致；验证：重跑主回放；风险：过早升格非最优版本
- [x] 3.2 更新 change 结论与回退说明，DoD：tasks/结论完整；验证：人工核对；风险：成功/失败表述失真
