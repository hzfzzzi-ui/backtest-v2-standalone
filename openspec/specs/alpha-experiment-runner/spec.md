# alpha-experiment-runner Specification

## Purpose

记录历史 `run_alpha_v1.py` 能力的退役状态与替代路径，防止主规格继续把已退役脚本当成 active capability。

## Requirements

### Requirement: Alpha V1 运行脚本保持退役状态

系统 MUST 将 `run_alpha_v1.py` 视为历史能力，不再作为当前 active experiment runner 对外暴露或维护。

#### Scenario: 检查 active runner
- **WHEN** 维护者检查当前 active experiment runner 能力
- **THEN** 系统 SHALL NOT 要求 `run_alpha_v1.py` 仍然可用

#### Scenario: 查询历史实现
- **WHEN** 维护者需要查看 `run_alpha_v1.py` 的历史实现和最初需求
- **THEN** 系统 SHALL 引导其查看 archived change 或历史实现，而不是 main active flow

### Requirement: 退役后必须提供替代路径

系统 MUST 为历史 `alpha v1` 运行场景提供明确替代路径，包括公开 experiment surface 和当前内部运行访问层。

#### Scenario: 面向产品或前端的运行
- **WHEN** 调用方需要运行实验并消费标准产物
- **THEN** 系统 SHALL 使用 `config_json -> experiment_id -> manifest/artifact` 的公开实验表面

#### Scenario: 面向新的内部研究流程
- **WHEN** 研究脚本需要访问当前运行时
- **THEN** 系统 SHALL 基于公开契约或 `backend/core/tools/experiment_runtime_access.py` 构建新脚本
