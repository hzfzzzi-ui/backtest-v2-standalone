## Overview

本 change 让账户层开始控制 stock / ETF 预算，但不拆 ETF 角色，不直接改 stock alpha 或 regime。

## Budget Control Scope

- 账户层决定：stock vs ETF 预算
- stock 腿消费账户预算后再运行自身 alpha
- ETF 腿消费账户预算后再运行自身资产选择
- `50/50` 仅作为 allocator disabled 或 budget map 缺失时的 fallback

## Non-Goals

- 不拆 ETF 为 defense / core beta
- 不处理状态边缘现金释放
- 不改当前 ETF 内部弱势策略

## Verification Intent

- 预算权上收后，主 explain 应由账户层解释 stock / ETF 权重变化
- 主行为变化应归因于账户预算变化，而不是 ETF 内部 patch
