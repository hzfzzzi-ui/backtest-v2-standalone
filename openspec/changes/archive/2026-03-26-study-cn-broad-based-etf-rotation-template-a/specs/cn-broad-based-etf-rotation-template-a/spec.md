## ADDED Requirements

### Requirement: 模板 A 必须显式区分 A0 当前直跑版与 A1 目标正式版
系统 MUST 为“宽基轮动模板 A”定义两个明确版本：

- `A0`：基于当前已接通目录的可直跑版本
- `A1`：补齐标准中证1000 / 红利 ETF 后的目标正式版本

`A0` 与 `A1` 的差异 MUST 在模板定义中显式暴露，且系统 SHALL NOT 将 `A0` 代理资产静默伪装成 `A1` 正式资产。

#### Scenario: A0 版本暴露当前代理语义
- **WHEN** 用户查看模板 A 的 A0 定义
- **THEN** 系统 MUST 明确哪些角色使用当前代理资产
- **THEN** 系统 MUST 明确 A0 是“当前可直跑版”而不是正式完整池

#### Scenario: A1 版本暴露正式目标语义
- **WHEN** 用户查看模板 A 的 A1 定义
- **THEN** 系统 MUST 明确 A1 依赖标准中证1000 ETF 与标准红利 ETF
- **THEN** 在这些资产未接通前，系统 SHALL NOT 把 A1 标记为已就绪

### Requirement: 模板 A 必须定义宽基 beta 层的最小规则骨架
模板 A MUST 定义以下最小规则骨架：

- 月频主调仓
- `12M / 6M / 3M` 相对强弱评分
- `close > MA200` 且 `12M return > 0` 的绝对过滤
- `Top2` 等权持仓
- `cash` 与 `511010` 作为最小 fallback 对照

模板 A SHALL NOT 在首轮定义中混入行业 ETF 轮动、单独防守层或保险层逻辑。

#### Scenario: 模板 A 默认使用月频 Top2
- **WHEN** 系统展开模板 A 的默认实验定义
- **THEN** 默认调仓频率 MUST 为月频
- **THEN** 默认持仓构建 MUST 为 `Top2` 等权

#### Scenario: 模板 A 默认使用双条件绝对过滤
- **WHEN** 系统展开模板 A 的默认过滤定义
- **THEN** 绝对过滤 MUST 同时包含 `MA200` 与 `12M return > 0`

### Requirement: 模板 A 必须限制成长位和最小 AB 范围
模板 A MUST 将成长位限制为以下二选一：

- `159915`
- `588000`

模板 A MUST 将最小 AB 范围限制为以下四组：

- 成长位：`159915` vs `588000`
- 组合构建：`Top1` vs `Top2`
- fallback：`cash` vs `511010`
- 版本对照：`A0` vs `A1`

#### Scenario: 成长位不能同时占用两个槽位
- **WHEN** 系统展开模板 A 的单轮实验
- **THEN** `159915` 与 `588000` SHALL NOT 同时作为成长位进入同一轮最小实验

#### Scenario: 最小 AB 不得同时扩多个主变量
- **WHEN** 系统定义模板 A 的单轮对照实验
- **THEN** 单轮实验 MUST 只改变一个主变量
- **THEN** 系统 SHALL NOT 在同一轮里同时改成长位、fallback 与持仓数
