## 1. 配置中心单入口
- [x] 1.1 收敛顶栏配置入口为单一“配置中心”
- [x] 1.2 完成配置中心分组与命名映射（草稿 / candidate / 内置 / 已保存）

## 2. 运行真相统一
- [x] 2.1 实现前端 runtime config resolver
- [x] 2.2 统一 `run_async` 与 `execution_preview` 的 handoff 契约
- [x] 2.3 后端将 `config_id` 降级为 provenance，不再覆盖 runtime config json

## 3. 元信息与兼容
- [x] 3.1 在 `run_meta.json` 与 preview 返回中补齐 `resolved_config_mode/id/hash/source_type/owner`
- [x] 3.2 保留旧入口兼容层并隐藏旧 UI 暴露

## 4. 验证与归档
- [x] 4.1 完成 clean baseline / saved config / candidate 最小回归验证
- [x] 4.2 记录配置中心与运行真相迁移说明，约束后续 results-surface change
