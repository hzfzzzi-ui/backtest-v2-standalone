## Context

当前后端执行壳已经收敛到 `config_json -> compiler -> DataBundle -> foundation shell -> stage pipeline shell -> legacy adapter -> legacy execution kernel`，并且持续通过锁定基线 `exp_20260308_021045840_cde0` 的回归门禁。  
但公开表面仍然没有收敛：

- 运行入口仍暴露 `config_id`、`runtime_config_json`、`workbench_config`、`config_path` 等历史字段。
- 结果读取入口仍允许通过 `results_dir` 和隐式文件名直接读取产物。
- 历史与导出表面仍把 `report.html` 当成重要消费面。
- `_config_store`、`_candidate_presets`、`_experiment_history` 仍通过 `backtest_v2.py` 暴露在公开路由树上。

这意味着内部虽然已经接近单路径，但外部仍然存在多真相、多消费面和多兼容壳并存的问题。  
本 change 的目标不是重写引擎，而是把公开 API 和实验产物表面先收敛到你最初定义的后端目标：唯一 `config_json` 输入、唯一 `experiment_id` 输出、唯一 `manifest + artifacts` 消费面。

## Goals / Non-Goals

**Goals:**
- 把公开单次回测入口收敛为只接受前端语义 `config_json`。
- 把公开实验读取入口收敛为 `experiment_id -> manifest -> artifacts`。
- 让历史列表、加载、对比、导出在 `report.html` 缺失时仍然可工作。
- 明确旧公开表面的冻结边界和淘汰前置条件。
- 在整个收敛过程中继续以 `exp_20260308_021045840_cde0` 做结果不变门禁。

**Non-Goals:**
- 本 change 不修改回测引擎数学逻辑、不修改成交时点、不修改 9-stage 计算口径。
- 本 change 不立刻删除所有旧代码；先做公开表面收敛和冻结，再进入后续淘汰。
- 本 change 不要求前端一次性重写所有消费逻辑；允许先补新入口，再迁移旧调用。
- 本 change 不改变现有实验目录中的核心产物文件名。

## Decisions

### D1: 公开运行真相只允许 `config_json`

对外公开的单次运行与 preview 表面只允许前端语义 `config_json` 参与配置真相。  
`config_id`、`runtime_config_json`、`workbench_config`、`config_path`、内建 preset 等历史配置变异字段，在公开接口中统一视为冻结兼容字段并显式拒绝。

原因：
- 这与用户已经确定的“唯一配置来源”一致。
- 只有显式拒绝，才能阻止旧表面继续长新逻辑。

备选方案：
- 保留旧字段但规定“以 `config_json` 为准”。拒绝，因为这会继续容忍双真相输入。
- 把旧字段静默映射到 `config_json`。拒绝，因为调用方无法判断自己仍在使用旧表面。

### D2: 公开消费真相只允许 `experiment_id`

公开运行成功后，主响应以 `experiment_id` 为唯一锚点；其他信息只保留最小状态字段。  
公开读取入口以 `experiment_id` 定位实验目录，不再要求前端或脚本传 `results_dir`。

原因：
- 用户已经明确结果返回前端应是唯一实验 ID。
- `results_dir` 属于内部存储实现细节，不应该成为公开协议的一部分。

备选方案：
- 继续允许 `results_dir` 作为公开读取参数。拒绝，因为这会把内部目录布局泄漏到外部调用面。

### D3: `manifest.json` 成为唯一公开产物发现入口

所有公开的实验读取、加载、历史和比较能力，都必须先以 `manifest.json` 发现标准产物，再按 manifest 提供的相对路径读取。  
公开 API 可以继续兼容已有的 artifact read 实现，但外部协议必须切到 `exp_id + manifest` 模式。

原因：
- 这能把“实验目录里有哪些文件、哪些是标准产物、哪些是可选导出物”明确化。
- 这也是后续删除旧 artifact 补丁层的前置条件。

备选方案：
- 继续按约定文件名硬编码读取。拒绝，因为这会让历史兼容补丁层一直存在。

### D4: `report.html` 降级为可选导出物

`report.html` 继续允许存在，并允许通过导出入口打开；但它不再是历史列表、结果加载、实验对比和主结果渲染的前置条件。  
当报告缺失时，系统必须显式返回“导出物缺失/未生成”，而不是让实验主流程或历史读取失败。

原因：
- 当前基线门禁里唯一长期漂移项就是 `report.html`，说明它不适合作为收敛期主协议。
- 用户已经明确前端主消费面是实验目录产物，而不是报告 HTML。

备选方案：
- 把 `report.html` 继续维持为必需产物。拒绝，因为这会阻碍旧报告层淘汰。

### D5: `_config_store`、`_candidate_presets`、`_experiment_history` 进入冻结兼容层

这三层在本 change 后不再允许承载新的产品逻辑：
- `_config_store` 只保留历史读取/迁移用途。
- `_candidate_presets` 只保留锁定基线/研究脚本兼容用途。
- `_experiment_history` 只保留围绕 experiment folder 的历史索引与清理，不再承载“报告优先”的消费假设。

原因：
- 这些模块当前仍然是旧真相和旧表面的主要扩散点。
- 先冻结，再迁移，再删，风险最小。

备选方案：
- 立即删除旧模块。拒绝，因为前端与脚本仍有兼容依赖。

### D6: 收敛顺序先补新公开表面，再切前端，再删旧壳

迁移顺序固定为：
1. 增加 `exp_id` 驱动的 manifest/artifact 公开入口。
2. 在公开 run/preview 上拒绝旧配置变异字段。
3. 让前端和历史/对比表面迁到 `experiment_id + manifest`。
4. 用基线门禁验证无结果漂移。
5. 最后才进入旧公开壳淘汰 change。

原因：
- 这样能把“协议切换”和“旧代码删除”解耦。
- 一旦出现偏差，能快速定位是公开表面问题而不是引擎问题。

## Risks / Trade-offs

- [风险] 公开接口拒绝旧字段后，部分旧脚本会立刻失效  
  -> Mitigation：保留内部迁移 helper 与基线脚本专用路径，并在 change 中明确哪些脚本必须先迁移。

- [风险] 前端短期内需要同时理解旧读取方式和新 manifest 方式  
  -> Mitigation：先补新入口并让 manifest 保持向后兼容，待前端切换完成后再删除旧读取接口。

- [风险] `report.html` 降级后，历史“查看报告”按钮的体验会变化  
  -> Mitigation：导出入口改为 best-effort，并在缺失时返回显式状态，不影响主结果加载。

- [风险] `_config_store` 和 `_candidate_presets` 冻结后，研究脚本可能仍然隐式依赖它们  
  -> Mitigation：把它们列入退休门槛文档，要求脚本迁移到显式语义 `config_json` 或内部工具调用。

## Migration Plan

1. 为实验目录补充/规范 `GET manifest` 与 `GET artifact by exp_id` 公开入口，保留旧 `results_dir` 读取接口作为短期兼容层。
2. 在公开 `run` / `run_async` / `execution preview` 接口上，把历史配置变异字段改为显式拒绝，并保留内部兼容 helper 供基线脚本使用。
3. 调整历史列表、实验加载、实验对比与导出逻辑，优先消费 `manifest.json`，并在 `report.html` 缺失时显式降级。
4. 补充公开表面冻结文档，明确 `_config_store`、`_candidate_presets`、`_experiment_history` 与 artifact 补丁层的删除前置条件。
5. 每一步都执行 `python backend/scripts/baseline_regression_check.py --rerun --write-to-candidate`，只有核心产物继续 `PASS` 才允许推进。

回滚策略：
- 任一步若导致基线结果漂移或前端主结果读取失败，先回滚公开表面改动，不动执行壳和引擎计算核。
- 在旧读取入口仍保留期间，允许临时切回旧表面，但不得继续往旧表面新增需求。

## Open Questions

- 锁定基线 candidate preset 是否最终迁到独立内部脚本，而不是继续留在公开路由树中？
- 公开 preview 是否要保留“基于现有 `exp_id` 读取结果再做 preview”的模式，还是单独拆成内部诊断接口？
- `report.html` 缺失时，前端是直接提示“未生成报告”，还是改为优先触发前端本地导出？
