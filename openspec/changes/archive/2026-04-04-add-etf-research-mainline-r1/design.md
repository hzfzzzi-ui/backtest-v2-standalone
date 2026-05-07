## Context

当前仓库已经具备两类与 ETF 相关的研究基础：

- formal `cn-etf-beta-sleeve`，面向 Governor 约束下的低频 beta stabilizer
- research-only 的 broad-based standalone mainline / governed exposure policy 模板，面向独立收益线探索

新版 ETF 单腿架构已经把合同、执行、审计拆开，因此这次不需要再新增引擎能力。真正缺的是一条收口明确的研究主线：它既不能回退到 formal stabilizer，也不能继续停留在“池子/过滤器/暴露语义多变量同时漂移”的实验集合里。用户已经把方向定死：

- 独立收益主线
- research-only
- A 股偏多
- 黄金/债券只做防守
- 成长席位固定为 `588000.SH`
- 调仓频率 `biweekly`
- `RISK_OFF` 也允许继续小幅承接 A 股核心宽基

这意味着本次实现更像“落一条正式研究模板”，而不是继续发散研究参数空间。

## Goals / Non-Goals

**Goals:**

- 新增一条单变体、单窗口起步的 ETF 主线 study，直接可跑 `2012-2026`
- 保持实现完全站在新版 ETF 单腿架构之上，不新增策略引擎分支
- 明确资产角色分层：A 股核心承接、单一成长席位、双防守层
- 让 `RISK_OFF` 的“小幅承接”可解释且可审计：只允许 core slot，不允许 growth slot
- 提供最小 generated script 与测试，保证研究入口可回归

**Non-Goals:**

- 不修改 formal `cn-etf-beta-sleeve` 的 requirement
- 不扩展 `cn_etf` 受控目录之外的新 ETF
- 不把这次研究线直接升级为 baseline 或 combo 正式锚点
- 不同时研究新的过滤器族、候选池族和多 growth seat 机制

## Decisions

### 1. 用“新 study”落地，而不是改现有 broad_based 主线模板

决策：
- 新建 `research/studies/etf/cn_broad_based_research_mainline_r1.study.yaml`
- 不直接覆盖 `cn_broad_based_standalone_mainline.study.yaml`

原因：
- 现有 broad-based standalone mainline 仍承担历史对照意义，直接覆盖会破坏对照链
- 用户这次给出的身份、资产角色和弱市语义已经明显超出旧模板，应独立命名，便于回测 ledger 归因

备选方案：
- 直接在现有 `cn_broad_based_standalone_mainline.study.yaml` 中新增变体

不采用原因：
- 会继续把“主线模板”和“策略候选版本”混在一起，后续读配置不清楚哪条才是当前研究主线

### 2. 保持 research-only，但尽量不越出现有受控 ETF 目录

决策：
- 资产池只使用现有首波目录已覆盖的 ETF：`510050/510300/510500/512100/512890/588000/518880/511010`
- 不引入 `159845/510880` 这类当前不在首波受控目录中的标准替代物

原因：
- 这样可以直接复用现有 `cn_etf` research entry，不需要额外扩目录和补数据治理 spec
- 用户要的是先落一条主线并跑通回测，不是先改资产目录工程

备选方案：
- 直接引入 `159845`、`510880`

不采用原因：
- 会把这次策略落地变成“策略 + 目录治理”双改动，违反单轮单主改动纪律

### 3. 选择链固定为 `core_growth_slot`

决策：
- `core_slot_symbols` 负责 A 股核心承接
- `growth_slot_symbols` 只放 `588000.SH`
- `target_selected_count=1` 的弱状态下，利用 `core_growth_slot` 的 slot cap 机制压掉 growth slot

原因：
- 用户已经明确只保留 `588000.SH` 作为 growth seat
- 该选择链天然支持“强状态 core+growth 双席位，弱状态只保留 core”这一语义

备选方案：
- 使用 `global_top2_12_6_3`

不采用原因：
- 在弱状态下无法自然压制成长席位，解释性更差

### 4. 双防守采用“limited defense + 单债 fallback”双层表达

决策：
- `limited_defense_candidates` 使用 `[511010.SH, 518880.SH]`
- `defense_asset_weights` 设为债券优先
- `fallback_mode` 仍保留 `single_symbol + 511010.SH`

原因：
- 这样能同时满足“黄金+债券双防守”与“硬 fallback 仍以债券为主”的要求
- 不需要新增 fallback 机制

备选方案：
- 只用 `single_symbol` fallback

不采用原因：
- 无法表达双防守层

### 5. `RISK_OFF` 小幅承接写进研究语义，但只承接 core

决策：
- `RISK_OFF` 保留正的 `target_exposure`
- `target_selected_count_by_state_5.RISK_OFF = 1`
- 继续保留 `controlled_accumulation_mode = light_and_controlled_trans_down`

原因：
- 当前架构里，`controlled_accumulation_mode` 主要描述 LIGHT/TRANS_DOWN 分层承接；`RISK_OFF` 是否保留小幅风险，更适合由 state map 直接显式表达
- 这样语义更清楚：`RISK_OFF` 不是新 layering 模式，而是研究型状态预算选择

备选方案：
- 给 `RISK_OFF` 新增独立 accumulation mode

不采用原因：
- 会把这次实现升级为引擎语义扩展，风险过高

## Risks / Trade-offs

- [研究结果过于激进] → 保持 `RISK_OFF` 初版只给 `1` 个 core slot，并把成长席位显式压掉
- [策略收益仍然偏钝] → 第一轮先固定池子和角色，后续优先研究 absolute filter，而不是继续同时改多处
- [用户语义与 formal ETF sleeve 混淆] → spec 中明确标记 `research-only`，并保持不修改 formal `cn-etf-beta-sleeve`
- [研究入口回归破坏] → 增加 generated thin script 与最小 study contract test

## Migration Plan

1. 新增 ETF 主线 study yaml
2. 新增 generated thin script
3. 新增最小 unit test，锁定 study 的执行计划关键字段
4. 运行回归测试
5. 运行 `2012-2026` 实盘窗口回测并检查产物

回退策略：

- 删除新增 study、generated script、test 即可
- 本次不修改 formal ETF sleeve 或公共执行入口，不涉及跨系统回退

## Open Questions

- 无阻塞问题。本次直接按用户已拍板的策略身份落地，剩余只用回测结果来判断后续是否需要第二轮过滤器研究。
