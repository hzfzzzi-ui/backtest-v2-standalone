## 1. 冻结 formal ETF 合同

- [x] 1.1 定义 `formal_etf_pool_v1` 并在 ETF formal compile input 中落地 core beta / formal defense / excluded 集合；DoD: ETF formal 输入不再包含 `518880.SH`、`588000.SH`、`512890.SH`；验证: 单独导出 ETF sleeve `run_config.json` 对比 formal pool；风险: 资产池收窄后可能引发收益回落。
- [x] 1.2 将 ETF sleeve 正式身份收口为 `formal ETF stabilizer`，统一 `source_entry_type`、`strategy_role`、`local_policy_mode`、`governor_boundary_mode`；DoD: ETF sleeve 审计不再出现 `GOVERNOR_BOUNDARY_OUT_OF_SCOPE` / `SIGNAL_SEMANTICS_OUT_OF_SCOPE`；验证: ETF sleeve `audit.json` 中 reason codes 收敛；风险: 入口身份切换可能影响现有 explain 路径。

## 2. 打通组合 formal 来源链

- [x] 2.1 更新 unified combo 的 `component_source_contract`，使 ETF component 显式发布 `formal_alignment_status`、`formal_etf_pool_version` 与 formal source entry；DoD: 组合 `run_meta.json` 可直接说明 ETF 组件是否具备晋升资格；验证: 检查组合 `run_meta.json` / `audit.json` 顶层证据；风险: 组件来源元数据与现有前端读取口径不一致。
- [x] 2.2 清理 unified combo 顶层 `research_combo_only` 主真相，替换为 formal mainline 组合元数据；DoD: formal top-level truth surface 不再把 research-only 字段当主真相；验证: 对比组合 `run_meta.json` 字段差异；风险: 旧展示层若依赖 research-only 字段可能需要兼容层。

## 3. 收口 weak-state / fallback 正式边界

- [x] 3.1 将 weak-state defense / fallback 限定在 formal defense 与 formal core beta 范围内；DoD: formal weak-state target truth 中不再出现 research-only fallback 资产；验证: 检查 `TRANS_DOWN / RISK_OFF` 产物与 reason codes；风险: 弱势状态部署能力可能下降。
- [x] 3.2 将 research-only fallback reason family 从 formal output contract 剥离，仅保留到 internal diagnostics；DoD: formal explain / audit 只暴露 defense 与 core beta 的正式预算、目标与偏差；验证: 对比 formal output 与 internal diagnostics 字段；风险: 排障信息若迁移不全会影响诊断效率。

## 4. 审计与晋升验证

- [x] 4.1 单独重跑 ETF sleeve，要求 `etf_beta_sleeve = PASS`；DoD: ETF sleeve 单独审计通过 formal alignment；验证: ETF sleeve `audit.json` 全量核查；风险: formal 合同收紧后可能暴露新的边界缺口。
- [x] 4.2 将通过的 ETF sleeve 挂回组合并重跑组合审计；DoD: 组合 `overall_status = PASS` 且 `timing_alignment / universe_lineage / price_adjustment_integrity / accounting_integrity / etf_beta_sleeve` 全 PASS；验证: 复核组合 `audit.json`；风险: 组件切换后组合级证据汇总可能再次失真。
- [x] 4.3 对比正式候选组合与当前收益守门线；DoD: 新组合结果不明显差于 `13.30% CAGR / 0.4908 Sharpe / -31.39% MaxDD`；验证: 已输出 `verification_4_3_ab_report.md`，结论为“审计通过但收益守门未过，baseline 晋升 deferred”；风险: 审计通过但收益明显下滑，导致 promotion 不成立。

