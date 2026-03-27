## 1. 正式口径对齐定义

- [x] 1.1 新增 ETF 正式口径对齐 capability，并在 delta spec 中定义 `formal_mainline / research_only / do_not_promote` 三类分类；DoD：新 capability 与相关 delta specs 落地；验证：`openspec validate audit-cn-etf-formal-mainline-alignment --type change --strict`；风险：分类边界定义过宽导致后续实现仍可钻空子。
- [x] 1.2 盘点根目录正式策略文档中的 Phase 1 核心范围、limited defense candidate 与明确排除资产，固化为正式审计约束；DoD：proposal/design/specs 对正式资产边界描述一致；验证：交叉核对文档与 spec；风险：仍保留历史口径并存。

## 2. 正式主线与研究分支边界收口

- [x] 2.1 为 ETF runtime profile、study metadata 和实验产物设计显式正式分类字段；DoD：design 与 specs 明确字段和语义；验证：字段能映射到 `run_meta/audit`；风险：只在命名层体现，未进入产物真相。
- [x] 2.2 设计偏离原因输出，至少覆盖超范围资产、limited defense 越界、信号语义越界、输出 contract 越界；DoD：spec 中定义 divergence reasons；验证：每种越界都有可审计 reason；风险：偏离原因过粗，不能支持后续治理。

## 3. 实施与最小验证

- [x] 3.1 收口 ETF contract、provider、research audit 与 studies，使正式对齐状态成为统一真相；DoD：核心模块统一消费 formal alignment 定义；验证：最小单测与 smoke；风险：改动点分散，容易出现字段漂移。
- [x] 3.2 跑一条正式兼容路径与一条研究分支路径，验证分类正确；DoD：一条实验被标记为 `formal_mainline`，一条越界实验被标记为 `research_only` 或 `do_not_promote`；验证：检查 `run_meta.json` 与 `audit.json`；风险：当前没有现成正式兼容路径，需要先做保守判定。

## 4. 文档、回退与降级说明

- [x] 4.1 输出实现说明，列明当前 ETF studies/profiles 哪些保留为正式主线、哪些降级为 `research_only`；DoD：`implementation_notes.md` 写清对齐结果；验证：人工复核与正式文档一致；风险：遗漏历史研究分支。
- [x] 4.2 写明最小回退路径与回归命令；DoD：实现说明包含回退文件列表和回归命令；验证：命令可执行；风险：只描述回退方向，不足以支持实际撤回。
