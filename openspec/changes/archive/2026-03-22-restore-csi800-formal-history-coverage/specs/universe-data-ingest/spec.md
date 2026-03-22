## MODIFIED Requirements

### Requirement: 指数成分导入
系统 SHALL 提供 `CSI800` 指数成分导入链，并区分正式正式历史链与低保真 fallback。正式链 MUST 基于 `000906.SH` 的可审计正式历史链导入 `pit_index_constituents`，不得继续把缺覆盖的短历史或月度近似 patch 默认当作正式研究入口。

#### Scenario: 正式 CSI800 历史导入
- **WHEN** 执行正式 `CSI800` PIT refresh 或导入命令
- **THEN** 系统 MUST 导入由正式历史链物化步骤生成的 `changes.csv`
- **THEN** 导入后的 `pit_index_constituents` 中 `index_code='000906.SH'` 记录 MUST 使用单一 formal source label

#### Scenario: 低保真 fallback 保留但不得冒充正式链
- **WHEN** 用户显式运行旧月度脚本或其他低保真 fallback
- **THEN** 系统 MAY 允许生成近似 changes 文件
- **THEN** 这些记录的 source label MUST 明确包含 `monthly`、`approximate`、`static` 或等价低保真语义

## ADDED Requirements

### Requirement: CSI800 正式 refresh 必须阻止短历史误覆盖
系统 MUST 在 `CSI800` 正式 refresh 的导入阶段校验历史覆盖。若待导入正式链不能覆盖所需起点，且用户未提供长历史 seed 物化正式链，命令 MUST 在导入前失败并保持数据库不变。

#### Scenario: 裸 Tushare 抓取结果缺失 required_start
- **WHEN** 正式 refresh 只拿到从晚近日期开始的 `000906.SH` 历史，不能覆盖 `required_start`
- **THEN** 系统 MUST 跳过 `--replace-existing` 导入
- **THEN** 系统 MUST 输出结构化失败摘要，说明缺失起点和建议补充的 seed 路径

#### Scenario: 提供长历史 seed 后允许正式全量替换
- **WHEN** 正式 refresh 提供覆盖 `required_start` 的 seed CSV，并成功物化最终正式链
- **THEN** 系统 MUST 对 `pit_index_constituents(index_code='000906.SH')` 执行全量替换
- **THEN** 系统 MUST 输出 fetch/materialize/import 三段 summary 供人工复核
