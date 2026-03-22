# ARCHITECTURE

## 1. 系统定位

当前仓库的正式定位是:

- 个人多资产趋势配置系统
- 当前正式接入资产: A 股
- 当前正式主线: `baseline_V10.1`

本仓库不是通用脚本集合，也不是 `outputs/` 驱动的产物仓库。源码主路径以
`backend/api`、`backend/core`、`backend/research`、`frontend`、`research`、
`tests`、`openspec` 为中心。

## 2. 目录树

```text
backtest_V2_standalone/
├─ backend/
│  ├─ main.py
│  ├─ api/
│  │  ├─ backtest_v2/
│  │  ├─ mobile/
│  │  ├─ transactions/
│  │  └─ shared/
│  ├─ cli/
│  │  ├─ commands/
│  │  └─ managed/
│  ├─ core/
│  │  ├─ config/
│  │  ├─ data/
│  │  ├─ universe/
│  │  ├─ strategies/
│  │  ├─ engine_runtime/
│  │  ├─ engine_vector/
│  │  ├─ stage_pipeline/
│  │  ├─ portfolio/
│  │  ├─ services/
│  │  ├─ tools/
│  │  └─ audit/
│  ├─ research/
│  └─ scripts/
│     ├─ generated/
│     ├─ ops/
│     └─ archive/
├─ frontend/
│  ├─ app/results-workbench/
│  └─ assets/js/
├─ research/studies/
├─ tests/
├─ docs/
├─ examples/
├─ openspec/
└─ outputs/
```

## 3. 模块职责

### 3.1 `backend/main.py`

- FastAPI 装配入口
- 挂载 `backtest_v2`、`mobile`、`transactions`
- 托管桌面端静态资源

### 3.2 `backend/api/backtest_v2`

- 只承担公共 route、请求契约、响应适配、边界校验
- 不再作为实验索引/比较真相构建的长期宿主
- `history_impl.py` 当前是 API 包装层，正式宿主已下沉到
  `backend/core/services/experiment_history_service.py`

### 3.3 `backend/core/services`

- 应用服务层
- 正式承接实验查询、实验比较、实验运行编排、产物稳定化、移动端汇总等
- 当前与 `backtest_v2` API 的边界是:
  API 负责 public contract，service 负责真相构建与编排

### 3.4 `backend/core/tools`

- 运行器、配置访问、候选预设、产物访问等工具层
- 供 service 层复用

### 3.5 `backend/research` 与 `research/studies`

- 研究定义加载、study 编排、研究纪律落地
- `research/studies/*.study.yaml` 是正式研究定义面

### 3.6 `frontend`

- `frontend/index.html` 是桌面壳入口
- `frontend/app/results-workbench` 是 Vue 结果工作台
- `frontend/assets/js/state/config-draft-core.js` 是配置编译唯一 owner
- `frontend/assets/js/backtest_v2.js`、`ui-controls.js`、`artifacts.js`
  只允许继续承担 bootstrap、桥接、轻量控件联动

## 4. 路径边界

### 4.1 主路径

- `backend/api`
- `backend/core`
- `backend/research`
- `frontend`
- `research`
- `tests`
- `openspec`

### 4.2 过渡路径

- `backend/scripts`
- `backend/scripts/generated`
- `backend/core/cli`
- `frontend/assets/js/backtest_v2.js`
- `frontend/assets/js/ui-controls.js`
- `frontend/assets/js/artifacts.js`

这些路径允许维护，但不应继续吸收新的长期主逻辑。

### 4.3 产物路径

- `outputs`

`outputs/` 只保存运行产物，不是源码主干。

## 5. 正式入口

- HTTP 入口: `backend/main.py`
- CLI 入口: `python -m backend.cli`
- 研究入口: `backend/research/study_runner.py`
- 桌面入口: `frontend/index.html`
- Vue 结果区入口: `frontend/app/results-workbench/main.js`

## 6. 主运行链

当前主运行链是:

```text
backend/main.py
-> backend/api/backtest_v2/routes/*
-> backend/core/services/*
-> backend/core/tools/*
-> backend/core/engine_runtime + engine_vector + stage_pipeline + portfolio
-> outputs/experiments/<exp_id>/*
```

研究链是:

```text
research/studies/*.study.yaml
-> backend/research/study_runner.py
-> backend/core/services/experiment_runtime_service.py
-> outputs/experiments/<exp_id>/*
```

前端结果链是:

```text
frontend/index.html
-> frontend/assets/js/results-workbench-bridge.js
-> frontend/assets/js/pages/desktop-research-page.js
-> frontend/app/results-workbench/main.js
```

## 7. 协议与示例文档

正式协议文档位于:

- `docs/SCHEMA_rows.json.md`
- `docs/SCHEMA_run_meta.json.md`
- `docs/SCHEMA_manifest.json.md`
- `docs/RUNBOOK_baseline_regression.md`

最小示例目录位于:

- `examples/experiment_contract_minimal/`

## 8. 当前收口状态

- `backend/cli` 已是正式 CLI 面
- `frontend` 已冻结 owner map
- `backend/api/backtest_v2` 正在继续瘦身，方向是只保留边界层职责
- `outputs/experiments/<exp_id>` 是实验协议真相目录
