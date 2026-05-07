## Overview

本 change 先拆语义，不强制先拆代码运行实体。

## Budget Semantics

- `ETF defense budget`
  - 面向弱势承接
  - 以债/现金类为主
- `ETF core beta budget`
  - 面向核心宽基暴露与弱势小规模累积

## Explain Semantics

- explain 必须分别给出 defense / core beta 的目标预算、实际预算和偏差
- audit 必须能说明 ETF 持仓中哪些属于 defense，哪些属于 core beta

## Non-Goals

- 不要求立刻拆成两个独立 engine
- 不改 stock alpha
- 不改变账户层对 stock/ETF 的一级预算分配

## Verification Intent

- 用户可以在弱势环境中明确看到“防守仓”和“核心宽基累积仓”的角色差异
