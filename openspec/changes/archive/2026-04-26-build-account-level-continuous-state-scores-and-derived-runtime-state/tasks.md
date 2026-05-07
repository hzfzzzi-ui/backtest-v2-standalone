## 1. 分数目录与合同

- [x] 1.1 定义 account-level continuous state score catalog schema 与首版 3 个 score（`risk_on_score`、`recovery_score`、`defense_score`）；DoD: catalog 能固定声明 score 元数据、scope、标准化和 as-of 约束；验证: schema/unit 校验通过；风险: score 定义范围过大导致第二条 change 失控
- [x] 1.2 明确 `derived_state` 的四态解释映射合同；DoD: 研究层只能从连续分数派生 `BULL / TRANS_UP / TRANS_DOWN / RISK_OFF`；验证: spec 对照与样例输出一致；风险: 派生状态被误用成正式主线状态机

## 2. 日频快照产物

- [x] 2.1 建立账户层状态分数快照协议；DoD: `raw_value/normalized_value/availability_flag/asof_timestamp/source_trace/derived_state` 字段齐全；验证: 产物样例可生成且字段完整；风险: 字段过少导致后续研究归因不足
- [x] 2.2 实现窗口级 score snapshot 落盘与读取入口；DoD: 可按窗口生成并读取日频状态分数快照；验证: 样本窗口快照生成检查通过；风险: 研究层产物与后续 runtime 消费合同脱节

## 3. 研究入口

- [x] 3.1 提供账户层单分数研究入口；DoD: 不跑完整策略也能输出单分数研究结果；验证: 用 1 个 score 完成最小研究样例；风险: 又退回依赖完整回放链路
- [x] 3.2 提供账户层组合分数研究入口；DoD: 能基于多个 score 生成组合分数并输出研究结果；验证: 用 2 个 score 完成最小组合研究样例；风险: 组合 score 合同与未来 runtime score 合同不一致

## 4. 可观测性与回退

- [x] 4.1 为 score catalog / snapshot / study surface 补 focused tests；DoD: schema、快照、研究入口均有最小测试；验证: focused tests 通过；风险: 第二条 change 无法作为第三条 change 的稳定依赖
- [x] 4.2 输出最小研究说明与回退路径；DoD: 说明文件写清改动边界、验证方法、回退思路；验证: artifacts 可独立阅读；风险: 平台层改动没有明确 rollback 边界

