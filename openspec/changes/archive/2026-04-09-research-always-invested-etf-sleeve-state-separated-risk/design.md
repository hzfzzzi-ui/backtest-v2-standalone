## Context

当前账户层主真相、统一 transition contract 和 shared account execution owner 都已经到位。最新研究表明，继续围绕局部 weak-state patch 调整边界收益不高。更值得研究的是把 ETF sleeve 升级成一条 always-on 配置腿，让 ETF 在所有状态下保持非零持仓，并通过 `defense / core_beta` 分层与 A 股个股腿错开风险收益。

当前最直接的研究起点应保持简单：

- `defense` 先只用 `511010.SH`
- `core_beta` 先只用 `510300.SH`
- 不同时引入更多 ETF 标的
- 不改变当前账户层主 owner 结构

## Goals / Non-Goals

**Goals:**
- 定义 ETF always-on 研究合同，要求 ETF sleeve 在各状态下保持非零持仓
- 明确 `BULL / TRANS_UP / LIGHT / TRANS_DOWN / RISK_OFF` 下 ETF 的 `defense / core_beta` 风险分层
- 让共享账户执行 runtime 能解释 ETF 与个股腿的风险分工，而不是把 ETF 做成第二条高 beta 股票腿
- 为下一步最小 A/B 实验准备 apply-ready 的任务拆解

**Non-Goals:**
- 这条 change 不直接实现新执行逻辑
- 不扩展更多 ETF 标的
- 不修改股票腿 alpha 逻辑
- 不同时研究 transition hysteresis、cash release、entry/exit 微调

## Decisions

### 1. 先研究“ETF sleeve 全程非零持仓”，不先研究“更多防守 patch”
- 原因：当前结构问题已经解决，下一步更值得研究长期配置角色，而不是局部弱势补丁
- 备选：继续调 `defense establish` 强度
- 放弃原因：这条线已经证明边际收益低，而且容易把 ETF 限死在弱势辅助腿

### 2. ETF 风险分层只用 `511010.SH + 510300.SH`
- 原因：保持最小变量，先验证“always-on + 风险错开”是否成立
- 备选：同时引入黄金、短债、红利或更多宽基
- 放弃原因：变量过多，会影响归因

### 3. 优先验证“非零持仓率 + 相关性错开”，不先追 CAGR
- 原因：这条研究首先回答的是角色定位，不是收益极大化
- 备选：直接以 CAGR/Sharpe 作为主目标
- 放弃原因：容易重新回到收益优先、角色不清的老路

### 4. 保持账户层单一真相
- 原因：ETF always-on 的预算、执行解释和结果展示都必须继续由账户层主导
- 备选：在 ETF 局部 engine 里单独做 always-on overlay
- 放弃原因：会重新引入双重语义

## Risks / Trade-offs

- [风险] ETF 全程非零持仓会抬高总组合常态风险暴露 → [缓解] 第一轮只允许 `defense/core_beta` 二分，不上更多高 beta 标的
- [风险] ETF 与个股腿仍可能高度同向 → [缓解] 将“ETF 与个股腿相关性下降”列为主验证指标
- [风险] 增加 always-on 后可能牺牲收益或 Calmar → [缓解] 先做最小 A/B，不直接切主线
- [风险] 状态分层过细导致变量过多 → [缓解] 第一轮固定两只 ETF、固定状态映射，不研究更多路径
