## Context

当前 ETF 单腿的一个明确次级 bug 是：partial fallback fill 时，fallback 标的虽然原始目标权重为 `0`，但在 `_compress_research_mainline_live_targets()` 中会触发“任一标的为零即全体等权”逻辑，最终被写成显著偏大的 `target_weight`。由于 `order_sizing` 会把 `target_weight` 当作直接的 NAV 目标金额，这类错误不会在执行核内被纠正，只会落成 `SKIP_NO_CASH`。

## Goals / Non-Goals

**Goals:**

- 只修 ETF partial fallback fill 下的 `target_weight` 语义。
- 保证原始正目标标的继续承接 live target，零原始目标 fallback 标的在 partial fill 下保持 `0.0`。
- 保留 full fallback replacement 的既有部署能力。

**Non-Goals:**

- 不修改 benchmark gate。
- 不修改 ETF 绝对过滤器、growth slot 或研究状态语义。
- 不修改 execution kernel 的通用现金/lot/slot 逻辑。

## Decisions

### 决策 1：partial fill 仅压缩原始正目标权重

- 做法：在 `_compress_research_mainline_live_targets()` 中，如果选中集合里仍有原始正目标标的，则只在这些正目标标的之间按比例压缩 live target；零原始目标的 fallback 标的写回 `0.0`。
- 原因：fallback partial fill 的角色是补位，不应被当成完整 live seat。
- 备选方案：
  - 在 execution kernel 中特判 fallback：会把 ETF 语义泄漏进通用执行层。
  - 完全禁止 fallback buy：会改变研究语义，范围过大。

### 决策 2：full replacement 继续允许 fallback 承接 live target

- 做法：若选中集合中不存在任何原始正目标权重，则保持当前 full replacement 行为，由 fallback 选中集合承接 live target。
- 原因：这属于独立研究语义，不是本轮 bug。

## Risks / Trade-offs

- [风险] 修复后 ETF 单腿的“看起来还行”的部分暴露可能下降。  
  → 缓解：这是把错误 fallback 暴露去掉后的真实结果，应通过回测重新看结构而不是只看短期收益。

- [风险] full replacement 语义若误伤，会把 fallback 全部打空。  
  → 缓解：用独立测试覆盖 partial fill 和 full replacement 两条路径。

- [风险] 该修复可能只暴露更深的现金/持仓问题，而不会单独提升收益。  
  → 缓解：本轮目标只修合同错误，不承诺收益改善。
