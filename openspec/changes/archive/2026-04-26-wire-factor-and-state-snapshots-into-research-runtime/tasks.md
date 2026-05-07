## 1. Snapshot 输入合同

- [x] 1.1 定义 factor/state snapshot 的 research runtime 输入协议；DoD: 能统一声明 snapshot path、type、window、variant 与 lineage 最小字段；验证: schema/unit 校验通过；风险: 输入协议和前两条 change 的 snapshot 产物脱节
- [x] 1.2 明确 fail-fast 与可读错误边界；DoD: 缺失或不匹配 snapshot 时 runner 给出明确错误；验证: 异常路径测试通过；风险: fallback 重算重新污染研究口径

## 2. Research runtime 接线

- [x] 2.1 扩展 study runner 支持 snapshot-backed execution；DoD: runner 能识别并消费 factor/state snapshot；验证: 用最小 demo study 跑通；风险: 把 snapshot-backed 逻辑和正式回放逻辑耦合在一起
- [x] 2.2 统一 machine outputs 中的 snapshot lineage 输出；DoD: 研究结果带有 snapshot path、window、variant、config hash、source trace；验证: 样例输出检查通过；风险: lineage 不足以支撑后续审计

## 3. Demo 与测试

- [x] 3.1 提供最小 snapshot-backed 因子研究样例；DoD: 用已存在 factor snapshot 能完成最小研究样例；验证: focused tests 通过；风险: 第三条 change 只停在协议层
- [x] 3.2 提供最小 snapshot-backed 状态研究样例；DoD: 用已存在 state score snapshot 能完成最小研究样例；验证: focused tests 通过；风险: factor/state 两条线接口不一致

## 4. 可观测性与回退

- [x] 4.1 补 notes 与回退路径；DoD: 说明文件写清 research-only 边界、验证方法和回退思路；验证: artifacts 可独立阅读；风险: 后续误把第三条 change 当正式主线接线
- [x] 4.2 补 focused tests 并确认不影响现有主线；DoD: snapshot-backed runtime tests 通过且不引入主线行为变化；验证: focused tests 通过；风险: 平台层改动反向污染正式主线

