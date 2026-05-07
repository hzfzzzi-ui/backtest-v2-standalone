## 1. 新桌面壳与模块边界
- [x] 1.1 新增 `desktop-app-shell` 正式能力，固定单页 desktop app、顶层模块和统一宿主边界。
- [x] 1.2 将 `results-workbench` 降级为 `results_workspace` 子模块。

## 2. 状态与 API 边界
- [x] 2.1 将旧 state slice 定位为迁移原型，正式上引入单一 app state + 领域切片骨架。
- [x] 2.2 将 `api-shared-helper-surface` 收口到统一 API adapter，UI 层禁止直接 `fetch`。

## 3. 旧壳与过渡层降级
- [x] 3.1 将 `frontend-module-split` 改为围绕新 desktop app 拆分，而不是围绕旧壳。
- [x] 3.2 将 `multi-alpha-workbench-ui` 收口到 `config_workspace`，保留阶段式思路但重做交互。

## 4. 迁移说明与验收基线
- [x] 4.1 补充迁移顺序、验证与回退说明，形成 apply-ready 基线。

