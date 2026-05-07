## 1. 前端运行合同修复

- [x] 1.1 在 `config_workspace` 或共享 serializer 中实现正式 `FrontendSemanticConfig` payload 裁剪，确保运行与保存基线共用同一提交流水
  - DoD：前端不再向后端提交 `asset_context`、`unified_runtime`、遗留 `data_role` 包装字段
  - 验证：桌面端 `加载配置 -> 运行` 与 `保存基线` 回归、相关前端单测
  - 风险：误删仍被 workspace 本地依赖的辅助字段
- [x] 1.2 更新 `run_orchestration`、`save_orchestration` 与相关测试，锁定“草稿可含辅助字段、正式提交载荷必须裁剪”的边界
  - DoD：运行链不再触发 `invalid config_json`
  - 验证：Playwright 主工作流、前端边界测试
  - 风险：旧测试仍按未裁剪草稿断言

## 2. 文档与实现追平

- [x] 2.1 追平前端主文档，明确桌面壳当前已接管的范围和仍保留的 compat 现状
  - DoD：前端架构文档不再把未退出的 compat 写成已完全完成
  - 验证：人工对照 `index.html`、`desktop-shell/*` 实现
  - 风险：把过渡态写得过于理想化
- [x] 2.2 追平数据库主文档，明确事务域当前已进入 DB 主读写 + compat 回退阶段，并把 `data_role` 标记为 compat 而非正式上层合同
  - DoD：数据库文档与当前 PG 主路径一致
  - 验证：对照 `pg_env.py`、`ops_domain_pg.py`、相关表与文档表述
  - 风险：忽略仍存活的 compat 路径

## 3. 审计闭环与低频残留

- [x] 3.1 新增系统收口审计输出约定，并把其接入 cleanup 后验收
  - DoD：系统级重构后能统一检查文档漂移、主工作流和低频残留
  - 验证：更新 spec/文档并形成一份可复用检查清单
  - 风险：规则过宽导致后续执行成本过高
- [x] 3.2 清理本轮已确认的低频残留描述，包括已删除旧文件的 spec/test/comment 漂移
  - DoD：主 spec、边界测试和注释中不再继续描述已退出对象为主路径
  - 验证：全文检索 + 相关测试
  - 风险：误删仍有兼容意义的说明
