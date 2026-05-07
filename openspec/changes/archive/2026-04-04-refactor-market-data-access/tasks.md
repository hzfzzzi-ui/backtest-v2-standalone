## 1. 访问合同与入口骨架

- [x] 1.1 新增统一市场数据访问层骨架与能力接口定义。（DoD: 在 `backend/core/data` 下形成统一访问入口与最小能力接口；验证: 新模块可被导入且接口命名与 spec 一致；风险: 入口命名与后续实现不匹配）
- [x] 1.2 为统一访问层补齐固定输入维度与审计回显结构。（DoD: 能表达 `asset_scope / market / data_level / as_of_date|window / symbols` 及固定 audit 字段；验证: 单元测试或最小构造测试覆盖返回结构；风险: 提前固化过多字段导致后续迁移阻力）

## 2. Canonical L1 能力落地

- [x] 2.1 实现 `价格历史 / benchmark 历史 / 交易日历` 的 `L1 canonical` 读取路径。（DoD: 三类能力均通过统一入口返回最小正式字段；验证: 针对现有 canonical 对象做读取回归；风险: 旧表字段映射差异导致返回结构不一致）
- [x] 2.2 实现 `PIT 成分 / PIT 行业 / 证券主数据` 的统一读取路径。（DoD: 支持快照与切片、单标的与批量的约定能力面；验证: 基于现有 PIT 表做代表性查询回归；风险: PIT 有效期条件被错误改写）

## 3. 首批消费者迁移

- [x] 3.1 将 runtime compile 的正式市场数据入口改为 `canonical_market` source contract。（DoD: compile 不再把 `data_role` 与 `pams_ohlcv_daily` 作为正式默认入口；验证: `baseline_V10.1` compile 前后等价对照；风险: 旧 shadow/override 路径失效）
- [x] 3.2 将 `universe resolver` 改为通过统一访问层消费 PIT 与证券主数据。（DoD: 正式主路径中不再自行直查 `pit_*`；验证: `ALL_A / HS300_ZZ500 / INDUSTRY / CUSTOM` 对照回归；风险: universe 集合漂移）
- [x] 3.3 将 `market_snapshot_service` 改为通过统一访问层消费价格、日历与必要 PIT 数据。（DoD: 主路径不再直接依赖旧市场表名；验证: 指定交易日 snapshot 结构对照；风险: 快照层字段语义偏移）

## 4. Compat 收口与回归

- [x] 4.1 收紧 compat 入口语义，保留迁移壳但移除长期正式默认定位。（DoD: 旧 compat 仍可显式迁移使用，但新默认入口不再落到 compat；验证: compile/audit 可区分 canonical 与 compat；风险: 旧 baseline 脚本仍隐式依赖 compat）
- [x] 4.2 补齐文档、测试与回退说明，形成第一批实现的 apply-ready 回归面。（DoD: 相关 docs/spec/tests 与实现一致，且列出回退路径；验证: `baseline_V10.1` compile、resolver、snapshot 三组回归通过；风险: 文档与实现再次漂移）
