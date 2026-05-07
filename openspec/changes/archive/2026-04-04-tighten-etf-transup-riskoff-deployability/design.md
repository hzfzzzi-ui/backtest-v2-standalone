## Context

当前 ETF research mainline 已经具备独立 study、独立 contract 模块和独立 provider 模块，但 `governed_broad_based_standalone_mainline` 仍然复用了偏 formal stabilizer 的部署语义。结果是：

- `RISK_OFF` 有正 `target_exposure` 时，`deployment_pace` 仍可能被压成 `0.0`
- `TRANS_UP` 在非 rebalance 日只有一次性的状态切换补仓机会
- `BULL/TRANS_UP` 在非 rebalance 日默认走 `hold_until_rebalance`

这三点叠加后，研究主线虽然“纸面 target 很高”，实际组合却长时间停留在现金或旧 fallback 防守仓里，导致 `BULL/TRANS_UP` 的 target-actual gap 长期失控。

## Goals / Non-Goals

**Goals:**
- 让 ETF research standalone mainline 在 `RISK_OFF` 正目标暴露下拥有明确、非零的 deployability 合同。
- 让 `TRANS_UP` 在非 rebalance 日可以持续追平强状态缺口，而不是只在状态切换当天给一次机会。
- 让 `BULL/TRANS_UP` 在研究主线上出现 gap 时，可以通过明确的 gap-fill 路径追平目标暴露。
- 保持所有新增行为可审计，可从 `run_meta/audit` 直接判断 target、deployment、execution path 与 actual 的关系。

**Non-Goals:**
- 不改 ETF 池、RS 排序、绝对过滤主配置。
- 不改用户刚落地的 study 参数。
- 不动 formal ETF stabilizer 的主语义与 combo 主链。
- 不为了减少 gap 去隐藏 target，而是让 actual 真正接近 target。

## Decisions

### 1. 只对 research standalone mainline 改部署合同

`governed_broad_based_standalone_mainline` 与 formal stabilizer 分开处理。  
原因：这轮目标是修 research-only 主线的 deployability，不应该把 formal 主边界一并带动。

备选方案：
- 直接改所有 ETF 角色的部署公式。放弃，因为会污染 formal 口径。
- 只改 study 配置。放弃，因为当前瓶颈已证明在 contract/provider，不在 study 字段。

### 2. `RISK_OFF` 正目标暴露必须变成正部署能力

当 standalone mainline 在 `RISK_OFF` 下给出正 `target_exposure` 且不存在 Governor hard block 时，合同侧必须给出非零 `deployment_pace`，并允许 provider 生成 core-only 的小幅补仓。

备选方案：
- 继续保留 `RISK_OFF_ZERO`，只改审计口径。放弃，因为这会制造假 target。
- 直接让 `RISK_OFF` 满仓跟 target。放弃，因为与“弱市小幅承接”的研究意图不符。

### 3. `TRANS_UP` 从一次性 redeploy 升级为持续 recovery fill

非 rebalance 日的 `TRANS_UP` 不再只依赖状态切换边缘，而是在 gap 仍显著存在时允许继续沿着 core/growth 当前目标组合补齐。

备选方案：
- 保持只在状态切换日补一次。放弃，因为当前结果已经证明这条路几乎不生效。
- 直接把调仓频率改成 weekly。放弃，因为本轮用户要求先只动部署合同。

### 4. `BULL/TRANS_UP` 引入强状态 gap-fill 执行路径

research standalone mainline 在强状态下，只要 `actual_exposure` 明显低于当日 target，provider 就允许发出 gap-fill BUY，而不是默认 `hold_until_rebalance`。  
这个路径只做补齐，不改当日排序逻辑，也不新增卖出重平衡。

备选方案：
- 只改 `TRANS_UP`，不碰 `BULL`。放弃，因为当前 `BULL` 的大量零暴露日也来自“持续等待 rebalance”。

## Risks / Trade-offs

- [风险] 调仓频率表面上仍是 `biweekly`，但实际 BUY 会更频繁。  
  → 缓解：新增专属 execution path 和 reason_code，确保可审计。

- [风险] gap-fill 可能提高换手和回撤。  
  → 缓解：先只做 BUY 侧补齐，不引入非 rebalance 卖出重平衡。

- [风险] `RISK_OFF` 小幅承接可能与绝对过滤冲突。  
  → 缓解：优先走 core-only 小额补仓，并把 override 原因写入 diagnostics。

- [风险] 如果 `BULL/TRANS_UP` 仍达不到 `10%` 目标，可能说明过滤或 seat 结构也是瓶颈。  
  → 缓解：本轮先把 deployment path 的锅单独排干净，再决定是否开下一轮 spec。
