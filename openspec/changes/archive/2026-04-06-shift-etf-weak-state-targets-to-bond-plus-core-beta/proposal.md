## Why

当前 `A_STOCK_ETF_V1` 的 ETF 弱势承接已经从“被再平衡节奏直接挡掉”收敛到了“进入防守执行链后被 execution constraint 拒绝”，说明主问题已不再是时点门禁，而是弱势目标结构本身仍偏“纯防守空仓化”。在“个人多资产趋势配置系统”的定位下，`RISK_OFF` 不应长期表现为接近空仓，而应表现为“防守优先、允许少量核心宽基累积”的低风险承接状态。

## What Changes

- 将 ETF 弱势正式目标映射改成“债 + 少量核心宽基”的累积结构。
- 在 `RISK_OFF` 中移除黄金的正式承接角色，改为 `511010.SH 70% + 510300.SH 30%`。
- 在 `TRANS_DOWN` 中采用债为主的过渡累积结构，改为 `511010.SH 55% + 510300.SH 45%`。
- 保持 ETF 弱势状态总暴露、stock 腿、regime、50/50 组合结构、execution constraint 逻辑不变。

## Capabilities

### New Capabilities
- `etf-weak-state-bond-plus-core-beta-policy`: 定义 ETF 弱势状态下“债 + 核心宽基”正式目标映射与资产边界。

### Modified Capabilities
- `cn-etf-beta-sleeve`: ETF beta sleeve 的弱势正式目标从“纯 defense 候选”收口到“债为主 + 少量核心宽基”的正式结构。

## Impact

- 影响代码：
  - `backend/core/config/etf_beta/*`
  - `backend/core/engine_vector/etf_beta/*`
  - `backend/core/stage_pipeline/adapters/*`
- 影响运行产物：
  - ETF standalone 的 formal/research view
  - `A_STOCK_ETF_V1` 组合中的 ETF sleeve explain 与持仓结构
- 不影响：
  - stock alpha 主逻辑
  - regime 定义
  - combo 50/50 主结构
