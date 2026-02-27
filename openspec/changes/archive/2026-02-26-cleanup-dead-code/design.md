## Context

项目从完整交易管理系统独立而来，前端保留了 8 个不再使用的 JS 文件（cashflow、dashboard、strategy、watchlist、holdings 系列、旧版 backtest），后端有 3 个死函数和 2 个 410 废弃端点。`index.html` 仅引入 `backtest_v2.js`，其他 JS 文件完全孤立。

## Goals / Non-Goals

**Goals:**
- 删除所有未被引用的前端 JS 文件
- 删除后端已确认的死代码（未被调用的函数、废弃端点、临时脚本）
- 确保删除后 Docker 构建和回测功能正常

**Non-Goals:**
- 不重构现有代码结构
- 不删除 `utils.js` 以外任何有可能被间接引用的文件（需先确认）
- 不清理后端尚有调用者的冗余代码（如同步版 `/experiment/run`）

## Decisions

### 1. 直接删除而非注释/标记
**选择**：直接删除文件和函数，而非添加 deprecated 注释。
**理由**：代码在 git 历史中有完整记录，标记只会延续混乱。这些文件已确认零引用。

### 2. 保留 `utils.js` 的判断标准
**选择**：检查 `backtest_v2.js` 和 `api.js` 是否 import 了 `utils.js`，若无引用则删除。
**理由**：`utils.js` 文件名通用，不能仅凭"看起来没用"就删除，需代码级确认。

### 3. 保留同步版 `/experiment/run` 端点
**选择**：暂不删除 `POST /api/backtest_v2/experiment/run`（同步版）。
**理由**：虽然前端未使用，但它是一个完整的功能端点（非 410），可能有外部调用者或调试用途。

### 4. 保留 `GET /results/{run_id}` 端点
**选择**：暂不删除。
**理由**：同上，是完整功能端点，可能被外部工具使用。

## Risks / Trade-offs

- **[风险] 删除后发现某文件有隐式依赖** → 缓解：git 可回退；删除前已通过 import/引用分析确认无依赖
- **[风险] 后端死函数实际被反射或动态调用** → 缓解：三个函数无任何字符串引用，且函数名以 `_` 开头表明为内部函数
