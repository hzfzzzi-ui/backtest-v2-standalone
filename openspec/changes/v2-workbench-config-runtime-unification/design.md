## Context

当前 workbench 的配置链路同时保留了历史遗留和新增 candidate 逻辑：
- 顶栏有 `preset` 入口
- 顶栏又有快速 `加载`
- 还残留隐藏的 `configList / loadLatest`
- 运行时可能同时提交 `config_id` 和 `workbench_config`

这会导致三个问题：
1. 用户无法判断当前运行到底以哪份配置为准。
2. `run_async` 与 `execution_preview` 的配置来源可能不一致。
3. 结果页与历史页无法稳定解释“本次实验来源于哪条配置链路”。

这个变更必须先完成，因为后续结果页、漏斗和 UI 重排都依赖“配置唯一真相”。

## Goals / Non-Goals

**Goals:**
- 前端只保留一个配置加载入口，名称为“配置中心”。
- 运行与预览都只接收一份 resolved runtime config json。
- `config_id`、builtin 模板、candidate preset 仅用于来源记录与快速选取，不再与草稿并行争夺运行真相。
- 配置列表命名与展示分组统一，用户能一眼区分“草稿 / 已保存 / 内置 / candidate”。
- 每个实验都在 `run_meta.json` 中写清 `resolved_config_mode / resolved_config_id / resolved_config_hash / source_type / owner`。

**Non-Goals:**
- 本 change 不重做结果页排版。
- 本 change 不改变回测引擎参数语义。
- 本 change 不清理历史实验目录，只治理未来运行与配置中心展示。

## Decisions

### D1: 前端只保留一个“配置中心”入口

顶栏保留一个入口，承载四类来源：
- 当前草稿
- 已保存配置
- 内置模板
- 锁定 candidate

`presetSelect` 与 `quickLoad` 不再并列暴露给用户。candidate 也通过配置中心统一呈现，而不是单独再放一个平行选择器。

原因：
- 同屏多个入口会让用户不知道“当前是加载配置还是 preset 覆盖”。
- 配置中心可以同时展示来源、锁定状态、是否可编辑、是否会覆盖草稿。

### D2: 运行前必须先解析为一份 runtime config

前端在点击运行或执行预览前，先统一做 `resolveRuntimeConfig()`：

```text
草稿 / 已保存 / 内置 / candidate
          ↓
resolved runtime config json
          ↓
run_async / execution_preview
```

请求体中只保留一个运行真相字段，后端必须以该字段编译运行时配置。`config_id` 只作为 provenance 附带，不再与 runtime json 并行决策。

原因：
- 这是研究纪律要求的“配置唯一真相”。
- 这样 Codex 直接调 API 与前端手动运行能共用同一协议。

### D3: 配置 catalog 统一命名与分组

列表展示拆成：
- 基线 / 官方模板
- Candidate
- 用户保存
- 脚本生成

命名约束：
- `display_name` 面向前端展示
- `name` 面向内部标识
- 展示时强制补充简短标签，如 `内置`、`锁定`、`脚本`

原因：
- 目前 `cfg_<hash>`、`cfg_flow_*`、`cfg_champion_*`、`cfg_clean_baseline_*` 混在一起，不具备可读性。

### D4: preview 与 run 的配置来源必须完全同构

`execution_preview` 与 `run_async` 使用相同的 runtime config resolver、相同的 provenance 字段、相同的冲突策略。

原因：
- 预览与正式运行不一致，会导致“前端看见的执行计划”和“回测真实执行”分叉。

### D5: 旧入口先兼容，后下线

第一阶段兼容旧控件和旧字段，但 UI 只暴露新入口；第二阶段再移除内部旧代码。

原因：
- 可以降低一次性重构风险。
- 便于对照验证新旧运行结果是否一致。

## Risks / Trade-offs

- [风险] 运行协议调整后，旧的前端事件绑定和脚本入口可能失效  
  → Mitigation：先做兼容层，保留旧字段解析但不再对用户暴露；补 API 对照测试。

- [风险] 历史配置命名不规范，强制统一展示可能造成短期辨识困难  
  → Mitigation：保留原 `config_id`，新增清晰的 `display_name / badge / source_type` 展示。

- [风险] candidate preset 与普通 saved config 的 provenance 容易混淆  
  → Mitigation：在配置中心明确单独分组，并在 `run_meta.json` 中始终写出 candidate 来源字段。

## Migration Plan

1. 先实现前端配置中心与 runtime resolver，不改引擎语义。
2. 后端 run/preview 同步接受统一 handoff，并保留旧字段兼容一段时间。
3. 核对 baseline / saved config / candidate 三条路径在 clean data 上的运行结果一致性。
4. 确认稳定后，再删除旧的双入口 UI 和隐藏 load path。

## Open Questions

- candidate 是否应该继续在顶部提供快捷入口，还是完全并入配置中心？
- `cfg_<hash>` 这类历史配置是否需要批量补 `display_name`，还是仅在 UI 展示时映射？
