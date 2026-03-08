## ADDED Requirements

### Requirement: 公开产物读取只认 manifest 声明
公开产物读取 SHALL 以 `experiment_id + manifest declared rel_path` 为唯一真相。系统 MUST 拒绝不在 manifest 中声明的 rel_path，并且 MUST 不再要求客户端提供 `results_dir`。

#### Scenario: manifest 声明产物可读取
- **WHEN** 客户端提供 `exp_id` 与 manifest 中声明的 rel_path
- **THEN** 系统返回对应产物内容

#### Scenario: 非声明路径被拒绝
- **WHEN** 客户端尝试读取 manifest 未声明的 rel_path
- **THEN** 系统拒绝请求，且不会暴露 experiment 目录中的其他文件
