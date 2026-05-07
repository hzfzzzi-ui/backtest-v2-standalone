## Overview

本 change 是最终切换阶段。

## Runtime Truth

最终 runtime 真相变为：
- account allocator output
- defense / core beta / alpha budgets
- sleeves 只消费预算与约束

## Cutover Scope

- 输入合同从 fixed combo wrapper 过渡到账户预算合同
- explain/audit/report 全部优先解释账户预算层
- 旧 `50/50` 只保留为基线、benchmark 或 fallback 参考

## Non-Goals

- 不在本阶段重新发明 stock alpha
- 不在本阶段引入新市场
- 不同时做额外收益增强实验

## Verification Intent

- runtime 顶层解释和行为由账户层统一驱动
- sleeves 成为执行消费者
- 旧 combo 真相不再是主路径
