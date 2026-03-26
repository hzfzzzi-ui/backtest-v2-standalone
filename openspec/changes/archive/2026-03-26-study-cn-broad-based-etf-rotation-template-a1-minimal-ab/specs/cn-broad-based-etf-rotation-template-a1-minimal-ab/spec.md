## ADDED Requirements

### Requirement: 模板 A1 最小对照必须使用标准资产共同覆盖窗口
系统 MUST 使用标准中证1000 ETF `159845.SZ` 与标准红利 ETF `510880.SH` 的共同有效覆盖窗口定义模板 A1 的最小对照窗口。

#### Scenario: A1 研究窗口按标准资产最短覆盖确定
- **WHEN** 系统运行模板 A1 最小对照
- **THEN** 研究窗口 MUST 不早于 `159845.SZ` 的真实覆盖起点
- **THEN** 系统 SHALL NOT 继续使用 A0 `2016-2026` 窗口直接运行 A1

### Requirement: 模板 A1 最小对照必须复用模板 A 的最小 AB 结构
系统 MUST 在 A1 中至少保留以下三组最小对照：

- 成长位：`159915` vs `588000`
- 组合构建：`Top1` vs `Top2`
- fallback：`cash` vs `511010`

#### Scenario: A1 不得同时改多个主变量
- **WHEN** 系统定义 A1 最小对照实验
- **THEN** 单轮实验 MUST 只改变一个主变量

### Requirement: 模板 A1 必须显式使用标准资产而非 proxy
系统 MUST 在模板 A1 中显式使用：

- `159845.SZ` 作为标准中证1000 ETF
- `510880.SH` 作为标准红利 ETF

系统 SHALL NOT 在 A1 中继续输出 `template_proxy_map` 作为主资产语义。

#### Scenario: A1 audit 显示标准资产语义
- **WHEN** 系统输出 A1 的 `audit.json`
- **THEN** 证据中 MUST 能看到 A1 role map
- **THEN** 若存在 proxy 字段，MUST 为空或明确为未使用

### Requirement: 模板 A1 结论必须与 A0 长窗口结论分开叙述
系统 MUST 将 A1 的结论表述为“标准资产共同覆盖窗口下的 A1 结论”，而不是直接与 A0 `2016-2026` 长窗口结论做一对一绝对比较。

#### Scenario: compare summary 标注 A1 窗口限制
- **WHEN** 系统输出 A1 compare/summary
- **THEN** MUST 明确写出 A1 的有效窗口
- **THEN** MUST 明确提示 A0 `2016-2026` 与 A1 `2021-2026` 不能直接横比
