## ADDED Requirements

### Requirement: 后端脚本必须显式选择调用表面
后端脚本在公开表面收敛后 MUST 显式声明自己属于 `public caller`、`internal helper caller` 或 `frozen legacy script` 之一。  
脚本 SHALL NOT 再以“历史兼容”为理由混用公开新表面与公开旧字段。

#### Scenario: 产品契约脚本走公开表面
- **WHEN** 某个脚本属于 smoke、公开契约验证或产品侧消费脚本
- **THEN** 该脚本 MUST 只通过公开 `config_json -> experiment_id -> manifest/artifact` 表面工作

#### Scenario: 旧脚本仍需历史排序或成本参数
- **WHEN** 某个脚本仍需要当前公开 `config_json` 契约未承载的历史排序、成本或研究专用字段
- **THEN** 该脚本 MUST 迁移到 internal helper，或被列入 `frozen legacy script` 清单

### Requirement: 后端脚本的产物消费必须围绕 experiment_id 与 manifest
后端脚本读取实验结果时 MUST 围绕 `experiment_id`、`manifest.json` 或显式 internal helper 工作。  
脚本 SHALL NOT 把公开运行返回中的 `results_dir` 或硬编码文件名重新当成产品真相。

#### Scenario: 公开脚本读取运行结果
- **WHEN** 某个脚本通过公开运行接口拿到成功结果
- **THEN** 它 MUST 从 `experiment_id` 出发继续读取 manifest 与声明产物

#### Scenario: 内部脚本确实需要目录路径
- **WHEN** 某个内部脚本必须访问实验目录路径以执行诊断、对比或补产物
- **THEN** 它 MUST 从 internal helper 获取该路径，而不是要求公开运行结果直接暴露 `results_dir`

### Requirement: 冻结脚本必须有明确治理信息
无法在本轮迁移的脚本 MUST 进入冻结清单，并记录原因、当前调用面、替代路径与退役触发条件。  
冻结脚本 SHALL NOT 再承载新产品逻辑。

#### Scenario: 某脚本暂时无法迁移
- **WHEN** 评估结果认定某个脚本在本轮无法安全迁移
- **THEN** 系统 MUST 将其记录到冻结文档，并标注 owner、阻塞原因与删除前置条件
