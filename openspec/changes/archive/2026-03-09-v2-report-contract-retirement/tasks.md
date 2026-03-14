## 1. 报告契约收口

- [x] 1.1 明确 Markdown/AI 报告为当前唯一主报告面，并补齐相关 spec delta。
- [x] 1.2 清理前端报告导出与查看入口，仅保留 Markdown 报告查看、复制与导出。

## 2. HTML 报告退役

- [x] 2.1 下线 `/api/backtest_v2/experiments/{exp_id}/report` 公开接口。
- [x] 2.2 将 `report.html` 从 manifest / artifact 主契约中移除，不再作为当前公开协议的一部分。

## 3. 脚本与门禁迁移

- [x] 3.1 更新 baseline gate，使其不再把 `report.html` 纳入当前主门禁或 WARN 来源。
- [x] 3.2 更新 consistency check，使其改为对核心 artifact 与 manifest/run_meta 自洽性做校验。

## 4. 验证

- [x] 4.1 验证前端仅通过 Markdown 报告查看与导出实验报告。
- [x] 4.2 验证移除 `report.html` 主契约后，核心 baseline compare 结果不受影响。
