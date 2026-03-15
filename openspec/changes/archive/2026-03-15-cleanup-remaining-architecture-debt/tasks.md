## 1. API Shared Helper 收口

- [x] 1.1 盘点 `backend/api/backtest_v2/*` 与 `backend/api/mobile/*` 仍在复用的历史 helper，并明确 `backend/api/shared/*` 的目标映射。
- [x] 1.2 创建并切换首批 `backend/api/shared/*` helper，使新 API 主路径不再直接依赖历史 `endpoints` helper。
- [x] 1.3 删除或压缩已被 shared 层接管的 `endpoints` helper，确保新 API 不再把历史目录当作真实基础设施。

## 2. Workbench 单 Owner 收口

- [x] 2.1 将 fallback 结果容器默认降级为 `hidden + inert`，只在显式调试或 Vue mount 失败时启用。
- [x] 2.2 继续把 `backtest_v2.js`、`ui-controls.js`、`artifacts.js` 中仍属活跃模块的逻辑外提到页面模块，旧文件仅保留接线与薄壳职责。
- [x] 2.3 移除生产主路径中对 fallback 结果 DOM 的直接可见渲染，主路径只保留 Vue workbench。

## 3. 脚本面高频迁移

- [x] 3.1 基于 `backend/scripts/inventory.json` 标记首批高频研究脚本与正式脚本的宿主目标。
- [x] 3.2 将首批高频研究脚本迁入 `.study.yaml` / `backend.cli study_run`，并为已维护 study 生成 canonical thin script。
- [x] 3.3 收缩顶层活跃脚本面，补齐 inventory / README / governance 规则，阻止新的顶层大脚本回流。

## 4. Canonical Artifact Migration

- [x] 4.1 实现历史 artifact / counter / shell label 的离线迁移器，并支持 dry-run 审计报告。
- [x] 4.2 分批迁移 `outputs/experiments` 到 canonical schema，更新 manifest / run_meta / physical artifact layout。
- [x] 4.3 删除运行时 alias 归一化主路径，使查询 / API / 前端只消费 canonical schema。

## 5. 回归与收口

- [x] 5.1 跑通静态边界、governance、protocol、workbench 相关测试集。
- [x] 5.2 以前后对照 `baseline_V10_1 -> exp_20260314_144548534_7db9` 复核 `perf/orders/trades/nav`，确认 `total_return/max_drawdown/cagr/sharpe/calmar/orders/closed_trades` 无漂移。
