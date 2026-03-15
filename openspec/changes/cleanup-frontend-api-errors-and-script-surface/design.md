## Context

当前仓库已经完成过三轮主干重构：

- `refactor-runtime-boundaries`
- `refactor-engine-execution-shell`
- `refactor-script-surface`

主边界已经建立，但仓库仍保留了较多“过渡期成功学”残留：

- 前端旧控制器仍然偏大：
  - `frontend/assets/js/ui-controls.js`
  - `frontend/assets/js/backtest_v2.js`
- 新旧 API 目录同时存在，旧 `backend/api/endpoints/*` 中仍有重型实现。
- 执行链仍保留 compat 通道：
  - `foundation_shell`
  - strict shim
  - `portfolio_builder.py`
  - `legacy_loop.py`
- 顶层脚本和本地临时产物已被治理，但还没有完全收缩成最小活跃面。

本 change 的目标不是继续大规模架构重做，而是把这些“过渡残留”继续压薄到可控状态，同时保持 `V10.1` 回归锚点 `exp_20260314_144548534_7db9` 的结果完全不变。

## Goals / Non-Goals

**Goals:**

- 继续削减前端桌面工作台旧控制器中的活跃职责。
- 继续压薄旧 API 目录中的 compat 实现，防止新代码继续落在 `endpoints/*`。
- 继续压缩执行 compat shim 的职责边界，明确删除路径。
- 继续压缩顶层脚本和工作区临时产物，防止脚本面与本地垃圾重新膨胀。
- 为上述清理补齐静态边界测试与回归门，确保 `V10.1` 口径不漂移。

**Non-Goals:**

- 不修改股票池、手续费、滑点、成交规则、调仓频率、仓位上限或 benchmark。
- 不引入新的策略逻辑、风险规则、信号公式或研究口径。
- 不改变 `V10.1` 的信号时点与执行时点。
- 不在本 change 内重写 `buildConfigDraft` 的业务语义。
- 不在本 change 内重写 `breakout_signal_provider.py` 或其他核心 provider 公式。

## Decisions

### 1. 以前端“职责外提”而不是“立即删除旧文件”为主

决策：

- 继续把 `backtest_v2.js`、`ui-controls.js` 中的职责外提到 `frontend/assets/js/pages/*`
- 旧文件先退化为薄壳、bootstrap 和少量过渡调用点
- 当静态边界测试稳定后，再删除 `_legacy...MovedTo...` 过渡函数

原因：

- 这是当前风险最低的清理路径
- 不会影响运行时协议
- 不会触碰 `10.1` 价格型信号时点

备选方案：

- 直接删除旧文件中的过渡函数
  - 放弃，原因是当前仍需确认 HTML 装载顺序和全局依赖点是否都已切干净

### 2. 旧 API 入口只允许保留 path 兼容，不允许继续持有重型实现

决策：

- `backend/api/endpoints/*` 继续存在时，只允许承担 path 兼容和薄转发
- 新逻辑必须进入 `backend/api/backtest_v2/*` 或 `backend/api/mobile/*`
- 反向从新实现 import compat 模块的路径必须被逐步清除

原因：

- 新旧目录双写是后续再次膨胀的主要风险之一
- path 兼容需要保留，但文件结构兼容不需要保留

备选方案：

- 立即删除所有 `endpoints/*`
  - 放弃，原因是当前仍有部分 compat 逻辑和 UI path 依赖，直接删除风险过高

### 3. 执行 compat shim 继续压薄，但不在本 change 内直接动价格型执行语义

决策：

- 继续收缩 `foundation_shell`、strict shim、`portfolio_builder.py`、`legacy_loop.py` 的职责
- 禁止这些文件吸收新执行逻辑
- 所有清理都必须以前后对照 `V10.1` 为门槛

原因：

- 当前最大的研究纪律风险仍然是执行口径漂移
- compat shim 清理可以推进，但不得拿 `10.1` 冒险

备选方案：

- 直接删除 compat 链
  - 放弃，原因是当前仍需保留过渡通道以支持现有运行面

### 4. 顶层脚本和工作区垃圾按“治理优先、删除次之”处理

决策：

- 已迁移脚本必须保持薄 wrapper
- 顶层历史脚本继续靠 `inventory.json`、`archive/` 和治理测试收口
- 本地临时目录、浏览器 profile、截图、`tmp_*` 产物继续通过 `.gitignore` 与清理规则约束

原因：

- 这类噪音会持续污染工作区和认知负担
- 但一次性删除所有历史脚本并不安全

备选方案：

- 直接批量删顶层脚本
  - 放弃，原因是会损伤可追溯性

## Risks / Trade-offs

- [前端全局依赖仍较多] → 先通过新增页面模块接管职责，再用静态测试确认旧函数不再是活跃入口。
- [API compat 清理可能误伤旧 path] → 保持旧 path 不变，只压缩文件内实现和反向依赖。
- [执行 compat 清理可能影响 `10.1` 结果] → 每轮清理后都复核 `exp_20260314_144548534_7db9` 的 perf / trades / turnover。
- [顶层脚本删除过快会损失审计链] → 先用 inventory 和 archive 收编，再逐步删除无价值 one-off。

## Migration Plan

1. 前端继续收缩：
   - 把剩余职责从 `backtest_v2.js`、`ui-controls.js` 外提到 `pages/*`
   - 用静态边界测试锁住“新文件承担活跃职责，旧文件只剩过渡壳”
2. API compat 清理：
   - 为 `backend/api/endpoints/*` 增加“薄 shim only”规则
   - 去掉新实现对 compat 模块的反向依赖
3. 执行 compat 清理：
   - 继续压薄 compat 入口
   - 禁止新逻辑进入 legacy 文件
   - 每步后复核 `V10.1`
4. 脚本与工作区治理：
   - 压薄剩余顶层 wrapper
   - 清理临时文件
   - 补治理测试

回滚策略：

- 前端拆分按模块回滚，保留旧 path 与旧入口
- 后端 compat 清理由小到大推进，任何一轮若影响 `V10.1` 即停止并回退该轮改动

## Open Questions

- `buildConfigDraft` 与 `applyConfigToUI` 是否应在下一轮单独起 change 做更细的配置状态面拆分。
- `backend/api/endpoints/*` 中哪些文件可以在下一轮真正删除，而不是继续保留薄 shim。
- `foundation_shell` 是否已经具备删除下一层 compat 依赖的条件，还是仍需再补一轮 golden。
