## Why

前几轮重构完成后，仓库里会残留一批明确的过渡壳、兼容入口、旧文档和历史路径。如果不单独起一个收尾 change：

- 旧壳会继续被误当成正式入口
- 旧 compat 层和旧 helper 会继续被新需求“顺手复用”
- 文档与实现会再次出现双份真相

因此需要把“残留清理”作为最后一个明确 change，而不是零散顺手删除。

## What Changes

- 新增 `post-refactor-residual-cleanup` 正式能力，定义重构后残留文件、目录、兼容入口与旧文档的清理条件。
- 收紧 `dead-code-removal`、`clean-dir-structure` 和 `script-surface-governance` 的适用范围。
- 明确只有在前序 change 完成并验证通过后，才允许删除旧壳、bridge、compat 入口和过期文档。

## Capabilities

### New Capabilities
- `post-refactor-residual-cleanup`: 定义残留文件清理、目录收口、过渡壳下线和清理回退要求。

### Modified Capabilities
- `dead-code-removal`: 仅在正式边界与验证完成后删除旧代码，不允许提前“大扫除”。
- `clean-dir-structure`: 目录清理必须服务于正式边界收口，而不是表面整理。
- `script-surface-governance`: 过渡脚本与旧入口必须显式标记并在收口后删除。

## Impact

- 主要影响模块：
  - `frontend/assets/js/backtest_v2.js` 及周边旧壳
  - 旧 bridge / 旧状态切片 / 重复 API helper
  - compat 入口与旧脚本
  - 已吸收的旧文档与附录
- 主要风险：
  - 删除顺序错误会破坏仍在使用的迁移壳
  - 容易把“未迁完但看起来旧”的文件误删
- 主要验证：
  - 前序 change 全部完成
  - 删除前后主工作流回归
  - 文档链接与入口回归
