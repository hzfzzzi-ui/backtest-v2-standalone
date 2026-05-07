## Context

当前正式 ETF stabilizer 的 `TRANS_UP` 同时存在两套互相冲突的语义：

- 合同模板仍保留 `tactical_overlay_cap`
- 执行合同与 seat 合同却始终只允许 `effective_max_positions = 1`

这会造成一个不可靠状态：预算模板像是在批准 `core + overlay`，但实际 order planning 和 portfolio runtime 永远只会放行单 seat。结果不是“overlay 等月末再部署”，而是 `TRANS_UP` 下的独立 satellite overlay 从 live 合同角度根本不可部署。

已有证据表明，这不是单纯节奏问题：
- `day_controls` 会把 ETF sleeve 压到单 seat
- `order_planning` 和 `portfolio_runtime` 会再次按剩余 slots 裁剪买单
- 最新正式 ETF 实验中，`TRANS_UP` 月末 BUY 也只落到 `core_accumulator`

因此，本次设计必须先消除合同矛盾，再谈后续收益优化。

## Goals / Non-Goals

**Goals:**

- 将 formal ETF stabilizer 的 `TRANS_UP` 明确定义为 `single-seat core recovery`。
- 让 `TRANS_UP` 的 live 目标、monthly path、state-change redeploy path 与单 seat 合同完全一致。
- 保留现有 Governor、`deployment_pace`、月频 rebalance 和 `TRANS_UP` floor redeploy 机制，不引入第二个 seat。
- 在日级和审计产物中明确标识 `TRANS_UP` 为单 seat core recovery，避免继续把纸面 overlay 解释成“漏部署”。

**Non-Goals:**

- 不修改 Governor exposure/seat 合同。
- 不把 `TRANS_UP` 扩展为双 seat 或受控 overlay seat。
- 不调整 ETF 池、RS 排序、BULL/TRANS_DOWN/RISK_OFF` 的主模板。
- 不在本次引入 `controlled_accumulation_mode != none`。

## Decisions

### 1. `TRANS_UP` 的 live 合同收敛为单 seat core recovery

选择：

- formal ETF stabilizer 在 `TRANS_UP` 下只保留 `core_accumulator` 的 live deployable target。
- `tactical_satellite` 不再作为 `TRANS_UP` 的独立 live 目标存在。

原因：

- 当前执行链只有一个 seat，继续保留独立 overlay 只会制造纸面预算。
- 这符合当前系统“先恢复底仓，再考虑更进攻配置”的 stabilizer 边界。

备选但不采用：

- 保留 `TRANS_UP` overlay，等未来节奏改动再部署。  
  否决，因为这会让系统继续保留已知不可执行的纸面合同。

### 2. 不改 `deployment_pace`，只对齐 `TRANS_UP` 目标语义

选择：

- `deployment_pace` 继续沿用现有定义。
- 本次只把 `TRANS_UP` 的 live target 语义对齐到单 seat，不扩大 pace，也不改 Governor 下发方式。

原因：

- 这样可以把变更限定在“合同一致性修复”，便于归因。
- pace 是下一层收益杠杆，但不是本次最小正确改动。

备选但不采用：

- 同时把 `TRANS_UP` pace 放大到 `floor + partial_overlay`。  
  否决，因为这已经是另一条 L3。

### 3. monthly 与 off-cycle 路径都必须服从同一单 seat 语义

选择：

- 月末 rebalance 下，`TRANS_UP` 只能选出单 seat 的 core recovery 目标。
- 现有 `TRANS_UP` 状态切换 redeploy 继续保留，但它的解释也必须是 core floor recovery，而不是 overlay 提前部署。

原因：

- 如果 monthly path 和 off-cycle path 对 `TRANS_UP` 语义不一致，审计仍会不可靠。

备选但不采用：

- 只改 redeploy path，不改 monthly path。  
  否决，因为月末路径同样会暴露合同矛盾。

### 4. 审计必须把“未部署 overlay”改写成“合同上不存在 overlay”

选择：

- research audit 与日级产物必须明确 `TRANS_UP` 当前是 `single-seat core recovery`。
- 审计不得把 `TRANS_UP` 下不存在的独立 overlay 再表述成“预算已批准但执行漏损”。

原因：

- 这次变更的目标就是去掉不诚实的纸面预算；审计如果继续沿用旧解释，会把正确行为误记为缺陷。

## Risks / Trade-offs

- [风险] `TRANS_UP` 的名义目标会下降，看起来像“更保守”。  
  缓解：这是把不可执行 overlay 从 live 合同中删除，不是新增保守限制；后续若要提高恢复期强度，应单开 L3 做双 seat 或 pace 变更。

- [风险] 过往实验的 `TRANS_UP target` 与新口径不连续。  
  缓解：通过 change 说明和 audit 字段明确这次是合同收敛，不与旧实验直接混作部署漏损比较。

- [风险] 用户会把这次收敛误解为 ETF 收益优化。  
  缓解：实现后必须同时报告行为变化与绩效变化，并明确本次主目标是合同一致性。

## Migration Plan

1. 先修改 ETF contract，使 `TRANS_UP` 的 live 目标不再包含独立 satellite overlay。
2. 再修改 provider 的 monthly selection / redeploy 元数据，使其与单 seat core recovery 对齐。
3. 补齐 `portfolio_daily.csv` 与 `audit.json` 的 `TRANS_UP` 合同解释字段。
4. 增加单测与实验回归，验证 `TRANS_UP` 不再产出第二个 seat 的纸面 target。

## Open Questions

- `TRANS_UP` 的 limited defense 是否保留为显式审计字段，还是完全折入 cash 解释。
- 后续若要提升 `TRANS_UP` 恢复强度，是优先开“双 seat overlay”还是优先开“partial overlay pace”。
