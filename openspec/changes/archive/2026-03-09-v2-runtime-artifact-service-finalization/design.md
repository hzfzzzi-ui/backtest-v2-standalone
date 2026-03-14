## 概述

这条 change 处理的是“后端分层最后一刀”，不是算法逻辑重写。

当前存在的问题：

1. `_experiment_runner_api.py` 既承担 public contract，又承担运行时编排。
2. `backtest_v2_artifacts.py` 既是 endpoint 辅助文件，又承担实验产物稳定化主逻辑。
3. 脚本层通过 `_internal_helper.py` 继续 import endpoint function，导致 service 边界没有真正成立。

本 change 的目标是把“运行服务”和“产物服务”抽到 core 层，让 API 变成 thin wrapper，脚本也直接调 service，而不是调 endpoint 内部实现。

## 目标

### 目标 1：建立 experiment runtime service

运行服务需要承接：

- public/internal request 归一化后的执行参数
- semantic config 编译结果
- `run_experiment()` 调用
- 运行异常与返回结果组装

其职责边界必须稳定，保证 API、脚本、基线门禁共享同一条运行服务，而不是各自绕路。

### 目标 2：建立 experiment artifact service

产物服务需要承接：

- `stabilize_experiment_result()` 的核心逻辑
- manifest 写入
- 标准产物补齐
- 产物访问共享函数

endpoint 文件只保留 HTTP 响应相关逻辑。

### 目标 3：脚本层不再 import endpoint

研究脚本、consistency check、baseline gate 与内部 helper 必须直接 import core service。

## 非目标

以下内容不在本 change 范围内：

- 不改 artifact 字段名与基线产物口径
- 不改回测引擎和 DataBundle 逻辑
- 不处理 `report.html` 是否退役；这属于下一条可选 change

## 设计

### 1. 运行服务

建议新增一个核心服务模块，例如：

```text
backend/core/services/experiment_runtime_service.py
```

对外提供稳定入口，例如：

- `run_experiment_request(...)`
- `preview_experiment_request(...)`

运行服务只接结构化输入，不直接依赖 FastAPI request model。

### 2. 产物服务

建议新增：

```text
backend/core/services/experiment_artifact_service.py
```

对外提供：

- `stabilize_experiment_output(...)`
- `write_manifest(...)`
- `ensure_standard_artifacts(...)`

`backtest_v2_artifacts.py` 退化为 HTTP 层包装或兼容导出层。

### 3. API thin wrapper

API 层职责：

- public contract 校验
- 调用 service
- 将 service 结果包装为 HTTP response

禁止 API 层继续承载运行期主要业务编排。

### 4. 脚本迁移

将以下链路迁移为 service import：

- `_internal_helper.py`
- `baseline_regression_check.py`
- `report_consistency_check.py`
- 仍在维护的研究脚本

目标是让脚本层对 API 实现零依赖。

### 5. 验证

必须继续使用基线 `exp_20260308_021045840_cde0` 进行逐次等价性校验，至少对比：

- `portfolio_daily`
- `portfolio_trades`
- `portfolio_candidates`
- `perf`
- `nav`
- `run_meta_core`
- `run_meta_universe`
- `config_truth`
- `manifest`

允许保留 `report.html` 的诊断性 `WARN`，但不得引入新的核心产物漂移。

## 风险与控制

### 风险 1：运行服务抽离引入口径漂移

控制：

- 每一刀都走 baseline compare
- API 只做 thin wrapper，不改运行配置来源

### 风险 2：脚本迁移导致历史研究脚本断裂

控制：

- 先迁 `_internal_helper.py`
- 再迁 live caller
- 冻结无 live caller 的旧脚本

### 风险 3：artifact service 下沉破坏前端读取

控制：

- manifest 和 artifact 文件名不得改变
- 前端继续通过 `experiment_id + manifest` 读取产物
