## 1. 宿主入口收口

- [x] 1.1 定义新桌面壳正式接管宿主入口与单一 root mount。（DoD: specs 固定默认宿主和挂载边界；验证: `openspec validate cutover-desktop-app-shell-host` 通过；风险: 旧壳入口仍被保留为正式路径）
- [x] 1.2 将 `results-workbench-snapshot-boundary` 收口到桌面 app state 持有。（DoD: bridge 降级为迁移工具；验证: delta spec 完整；风险: snapshot 双真相）

## 2. 共享边界收口

- [x] 2.1 将 `api-shared-helper-surface` 收口到统一 API adapter 边界。（DoD: UI 通过统一 adapter/transport 访问；验证: 旧 helper 降级为 compat；风险: API helper 双轨并存）
- [x] 2.2 在 `frontend-module-split` 中以新桌面壳为根重新界定模块边界。（DoD: 新桌面壳显式声明模块根、API 边界和 legacy compat 层；验证: OpenSpec validate 通过；风险: 模块边界与既有实现冲突）

## 3. 退出条件

- [x] 3.1 明确旧 `backtest_v2.js`、bridge、旧桌面 page controls 的迁移退出条件与回退顺序。（DoD: state/bootstrap 写明退出条件；验证: 回退路径可读；风险: 过早删除导致前端主链中断）
