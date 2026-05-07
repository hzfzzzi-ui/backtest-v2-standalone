## Overview

本 change 解决“状态切了但现金没释放”的结构问题。

## Core Design

- 仅在进攻态到弱势态的状态边缘触发，当前边界定义为 `BULL/LIGHT/TRANS_UP -> TRANS_DOWN/RISK_OFF`
- 释放动作是部分去风险，不是默认清仓
- 释放出的现金有明确去向：defense bucket 或 accumulation bucket
- explain 必须区分：
  - edge not triggered
  - edge triggered but no release required
  - edge triggered and partial release executed

## Scope Boundaries

- 不改变 regime 定义
- 不直接定义 ETF defense/core beta 预算拆分
- 不在本 change 中决定最终 accumulation 权重

## Verification Intent

- 进入 `TRANS_DOWN / RISK_OFF` 时，不再频繁出现“目标存在但一手现金都不够”的主失败形态
