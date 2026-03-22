## Why

当前 `pams_ohlcv_daily` 的问题不是单一字段缺失，而是主表行集、`daily_basic` 补齐、停牌建模、`moneyflow` 覆盖和审计口径混在一起，导致数据库即使继续补数据也无法证明“已经修好”。现在需要把 `pams_ohlcv_daily_v2` 的数据库补全目标单独固化为一条 change，明确什么必须补到零行缺口、什么允许软缺失、什么只能做侧表。

## What Changes

- 新增 `pams_ohlcv_daily_v2` 数据库补全合同，明确主表必须按 `security master x trade_cal(open days)` 生成 `CN_A` 应有行集，并将 `eligible_no_source` 视为构建失败。
- 新增 `v2` 原始层与 canonical build 约束，要求从 `Tushare` 原始源构建 `raw` 表，再生成 `pams_ohlcv_daily_v2`，不得继续 direct-to-final。
- 新增 `v2` 主表字段分层规则，区分硬字段、软字段和审计字段，并明确 `turnover_rate` 是唯一升格为主表硬字段的 `daily_basic` 字段。
- 新增 `pit_stock_moneyflow_v2` 侧表合同，明确 `moneyflow` 不得进入主表硬合同，且必须带覆盖率与空值治理。
- 新增 `v2` 审计表与构建门禁，要求逐日覆盖、逐字段空值、`v1/v2` 差异和异常样本可落库、可回放。
- 新增全历史回填与升格门槛，要求 `2007-01-04` 到 `2026-03-16` 完成回填后，只有通过三窗口审计才允许作为正式 shadow 数据源。

## Capabilities

### New Capabilities
- `cn-stock-daily-v2-database-completion`: 定义 `pams_ohlcv_daily_v2` 的零行缺口、核心字段零空值和字段分层合同。
- `cn-stock-raw-source-governance`: 定义 `v2` 所需的原始源落地、标准化、回填窗口和构建依赖。
- `cn-stock-moneyflow-v2-governance`: 定义 `pit_stock_moneyflow_v2` 的对齐、缺失治理和研究白名单门槛。
- `cn-stock-v2-audit-gates`: 定义 `v2` 的逐日审计、异常表、`v1/v2` 差异审计和升格门禁。

### Modified Capabilities
- 无

## Impact

- 受影响目录：
  - `backend/cli/managed`
  - `backend/cli/commands`
  - `backend/core/data`
  - `backend/configs`
  - `docs/db`
  - `openspec/changes/complete-pams-ohlcv-daily-v2-database`
- 受影响系统：
  - PostgreSQL schema
  - Tushare / AkShare 数据回填链路
  - `V10.1` 的 shadow 数据源编译入口
- 依赖：
  - `pit_security_master`
  - `trade_cal`
  - `daily`
  - `adj_factor`
  - `daily_basic`
  - `suspend_d`
  - `stk_limit`
  - `moneyflow`
