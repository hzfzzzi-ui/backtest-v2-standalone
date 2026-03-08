## 1. 公开运行入口收敛

- [x] 1.1 收紧公开 `run` / `run_async` / `execution preview` 请求模型，只接受 `config_json`，对 `config_id`、`runtime_config_json`、`workbench_config`、`config_path` 等历史字段显式报错；DoD: 公开接口不再接受配置变异字段，内部基线脚本仍保留兼容 helper；验证: 请求校验单测与接口级 harness；风险: 误伤仍在使用旧字段的内部脚本
- [x] 1.2 将公开运行成功响应收敛为以 `experiment_id` 为主的最小结果契约，并保证同步/异步完成态都能只靠 `experiment_id` 继续读取结果；DoD: 前端或脚本无需 `results_dir` 也能串起后续读取；验证: 运行接口定向测试与最小 smoke 调用；风险: 旧调用方仍隐式依赖 `results_dir`

## 2. Manifest 与 Artifact 公开表面

- [x] 2.1 增加并收敛基于 `exp_id` 的 manifest/artifact 读取入口，禁止公开读取未在 manifest 声明的相对路径；DoD: 存在稳定的 `exp_id -> manifest -> artifact` 读取链路；验证: manifest/artifact API 单测与路径越界测试；风险: manifest 声明不全导致合法产物被拒绝
- [x] 2.2 扩展 `manifest.json`，显式区分核心标准产物与可选导出物，并标记 `report.html` 的可用状态；DoD: manifest 能表达 `report.html` 存在/缺失且不影响核心产物发现；验证: manifest writer 单测与旧实验目录回填测试；风险: manifest 结构变化破坏前端兼容读取

## 3. 历史、对比与报告降级

- [x] 3.1 让历史列表、实验加载与清理逻辑围绕 experiment folder + manifest 工作，并单独暴露 `has_manifest` / `has_report` 等状态；DoD: 无 `report.html` 的实验仍可出现在历史列表并可被加载；验证: history API 定向测试；风险: 旧 index 记录缺少新状态字段
- [x] 3.2 将实验对比逻辑改为先读 manifest 再解析 `perf` 与 `nav`，缺少核心产物的实验显式标记为不可比较；DoD: compare 不再硬编码 `perf.json` / `nav.csv` 路径；验证: compare API 定向测试与缺产物样本测试；风险: 旧实验 manifest 不完整导致可比较样本减少
- [x] 3.3 将 `report.html` 导出正式降级为可选能力，报告缺失时返回显式 unavailable 结果而不阻断历史/主结果读取；DoD: 报告导出与主结果协议解耦；验证: report endpoint 定向测试与前端消费 smoke；风险: 前端仍把报告 404 视为实验失败

## 4. 冻结门槛与回归验证

- [x] 4.1 形成公开表面冻结文档，明确 `_config_store`、`_candidate_presets`、`_experiment_history`、旧 artifact 兼容补丁层的替代物与删除前置条件；DoD: 每类旧表面都有冻结范围、替代入口和删除门槛；验证: 文档审阅与 change 内引用完整；风险: 冻结边界描述不清导致后续继续往旧层加逻辑
- [x] 4.2 补充公开表面回归测试，并执行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`；DoD: 锁定基线 `exp_20260308_021045840_cde0` 的核心产物继续 `PASS`，若有 `WARN` 仅允许 `report.html` 诊断漂移；验证: baseline compare 报告与新增 targeted harness；风险: 公开表面改动意外触发配置真相或产物真相漂移
