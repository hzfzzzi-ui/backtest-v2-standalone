## Context

当前 `cn_etf_beta` 的研究语义仍然继承了“辅助 beta sleeve”历史路径：Governor 既提供统一状态真相，又通过过于保守的 deployability 与暴露响应把 ETF 压成低部署、低连续性的辅助层。这个语义适合服务个股 alpha 组合的边角配置，但不适合把宽基 ETF 当成独立主研究线来验证长期宽基轮动能力。

本次设计要解决的问题不是“把 ETF 从 Governor 中独立出去”，而是把边界重新划清：
- Governor/CTA 继续提供统一市场状态、总风险边界和禁做区间；
- 宽基 ETF 主线在这个边界内定义自己的进入、退出、承接和 fallback 逻辑；
- 研究范围只包含宽基 ETF，不引入行业 ETF、主题 ETF 或个股 alpha 组合层干扰。

这属于跨模块改动，会同时影响 ETF 合同、Governor 解释边界、ETF signal provider、research audit 和研究入口，因此需要单独设计。

## Goals / Non-Goals

**Goals:**
- 把 `cn_etf_beta` 的正式研究定位重定义为“受统一 Governor 管控的独立宽基轮动主线”。
- 定义宽基 ETF 主线专属的 exposure policy，包括 state-aware target exposure、enter/exit 逻辑、controlled accumulation 和 fallback 语义。
- 明确 Governor 只负责统一真相和风险边界，不再要求宽基 ETF 默认沿用个股 alpha 或辅助 sleeve 的风格暴露翻译。
- 让 `run_meta`、`audit.json`、ETF study summary 能清楚回答“Governor 给了什么边界”和“宽基 ETF 主线如何在该边界内独立决策”。
- 保持研究入口、study 配置和后端实现的合同一致，避免再次出现“研究目标变了，但 provider 和 audit 还沿用旧语义”的漂移。

**Non-Goals:**
- 不研究行业 ETF、主题 ETF 或 sector rotation。
- 不把 ETF 与个股 alpha 混成统一组合研究，也不推进 unified runtime。
- 不重写 Governor 主逻辑，不改变 canonical 5-state 真相源。
- 不在本轮扩展新的 ETF 数据源或新资产类别。

## Decisions

### 1. 保持统一 Governor/CTA 真相源，但引入宽基 ETF 主线专属的暴露翻译层

**Decision**
- Governor 继续输出统一的 `effective_state_5`、风险预算、drawdown/cooldown/defense 压力。
- 宽基 ETF 主线新增一层 `governed exposure policy` 翻译：把 Governor 的统一边界翻译成宽基 ETF 主线专属的 `target_exposure`、`min_deployable_exposure`、`controlled_accumulation_band` 和 `fallback_policy`。

**Why**
- 用户要求 ETF 仍受统一 CTA 管控，这意味着不能把 ETF 从 Governor 分叉出去。
- 但宽基 ETF 也不能继续按个股 alpha 那套“弱环境快速收缩、部署偏谨慎”的语义运行。

**Alternatives considered**
- 方案 A：让 ETF 完全脱离 Governor 独立运行。否决，因为会破坏统一风险真相与多资产中枢方向。
- 方案 B：继续使用当前辅助 sleeve 暴露语义。否决，因为已被多轮研究证明会把 ETF 压成低部署、低连续性辅助层。

### 2. 只研究宽基 ETF 主线，不允许行业 ETF 混入

**Decision**
- 本轮 study、配置合同和 audit 只允许宽基 ETF 主线。
- 成长位只允许“宽基风格增长代理”作为宽基研究的一部分，不能引入行业 ETF 或主题 ETF。

**Why**
- 当前用户明确要求只研究宽基 ETF sleeve。
- 如果同时引入行业 ETF，会把本轮研究目标从“独立宽基轮动主线”污染成混合轮动，结果无法归因。

**Alternatives considered**
- 方案 A：同时把行业 ETF 作为更快风格腿并入。否决，因为会一次改变候选池、风格暴露和 enter/exit 语义，违反最小改动原则。

### 3. 宽基 ETF 主线允许受控承接，但不得演化成无约束抄底

**Decision**
- 在 `LIGHT` 和受控 `TRANS_DOWN` 区间允许宽基 ETF 维持或分层增加部分暴露。
- 这种承接只能发生在 Governor 明确许可的带宽内，并且要有：
  - 最大目标暴露
  - 最小可部署门槛
  - 承接原因码
  - 受控 fallback

**Why**
- 用户明确指出，宽基 ETF 在大环境下跌时有理由拿到更便宜筹码。
- 但系统最高优先级是可信和可审计，不能把它实现成“越跌越买”的黑箱逆向策略。

**Alternatives considered**
- 方案 A：完全延续顺势退出，不允许承接。否决，因为这延续了辅助 sleeve 语义。
- 方案 B：在 `TRANS_DOWN` 或更弱状态无限制加仓。否决，因为会破坏 Governor 的总风险边界。

### 4. 研究结果必须显式拆分“Governor 边界”和“ETF 主线自有决策”

**Decision**
- `run_meta` 和 `audit.json` 中新增或强化两类字段：
  - Governor 提供的边界真相
  - 宽基 ETF 主线在该边界内的本地 enter/exit/deployability 决策
- audit 不能再只说“为什么今天 ETF 没仓位”，还要说“这部分是 Governor 压的，哪部分是 ETF 主线自己不进”。

**Why**
- 只有把两层真相拆开，才能判断本轮失败到底是 Governor 压制、绝对过滤过严，还是 ETF 主线自身逻辑无效。

**Alternatives considered**
- 方案 A：继续只输出统一的 sleeve budget。否决，因为无法区分上游边界和下游主线逻辑。

### 5. 研究入口显式标记为 standalone broad-based mainline

**Decision**
- 新研究入口、study 名称和 preset 摘要都必须显式表明这是“governed broad-based ETF standalone mainline”。
- 不再沿用“辅助 beta sleeve”“组合中的 ETF 分支”这种语义。

**Why**
- 研究目标变化后，如果入口命名仍沿用旧语义，会继续把实现拉回旧路径。

## Risks / Trade-offs

- [风险] 宽基 ETF 暴露语义放松后，回撤可能明显上升。  
  → 缓解：先做受控状态带宽与分层承接，不直接放开全状态高暴露。

- [风险] “受控承接”很容易被做成模糊抄底。  
  → 缓解：要求显式承接区间、承接 reason codes 和最大目标暴露，不允许黑箱式加仓。

- [风险] 研究入口虽然重定义成独立主线，但底层 provider 仍可能遗留旧辅助 sleeve 分支。  
  → 缓解：在 ETF 合同和 audit 里显式输出 `strategy_role`、`governed_boundary_source` 和 `local_policy_decision`。

- [风险] 只研究宽基 ETF 会牺牲短期收益上限。  
  → 缓解：这是本轮刻意选择的研究纪律，用来先稳定主线语义；行业 ETF 另开后续 change。

- [风险] 继续受统一 Governor 约束，可能仍然压制 ETF。  
  → 缓解：本轮的核心不是绕开 Governor，而是把 Governor 与 ETF 主线之间的翻译层做成 sleeve-specific policy。

## Migration Plan

1. 新增独立宽基 ETF 主线合同与研究入口定义。
2. 调整 ETF 配置 schema 与 contract owner，使宽基主线策略角色、暴露带宽、承接区间和 fallback 语义可配置。
3. 在 ETF provider 中实现 Governor 边界到宽基 ETF 主线本地决策的翻译层。
4. 扩展 audit / run_meta / summary，把 Governor 边界与 ETF 主线本地决策分开暴露。
5. 以单独 ETF 研究 study 验证，不与个股 alpha 混跑。
6. 如果结果不成立，可直接回退到当前 A0 主研究线，不影响个股主线或 unified runtime。

## Open Questions

- 本轮默认宽基 ETF 主线是否继续以当前 A0 资产池为起点，还是直接收缩到更纯的大盘/中盘宽基池？
- `controlled accumulation` 应否在 `TRANS_DOWN` 全部开放，还是只在更窄的带宽内开放？
- fallback 默认应优先 `511010` 还是 `cash`，是否需要双轨对照而不是单一正式口径？
