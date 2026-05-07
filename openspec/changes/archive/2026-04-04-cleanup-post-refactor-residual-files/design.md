## Context

本仓库已经明确区分：

- 主路径
- 过渡路径
- 产物路径

但在实际重构完成前后，仍会残留一批“已不再正式、但暂时还不能删”的对象。例如：

- 前端旧壳和 bridge
- compat 市场数据入口
- 旧状态切片和重复 helper
- 已被新文档吸收的旧说明文件
- 历史脚本和旧入口模块

因此残留清理不能和功能重构绑在一起，而应作为最后一个专门 change 处理。

## Goals / Non-Goals

**Goals**

- 定义哪些残留文件可以删
- 定义何时允许删
- 定义删除前验证与回退要求

**Non-Goals**

- 不在本次 change 中先行推进业务逻辑重构
- 不在本次 change 中为“看起来干净”做无关目录整理
- 不在本次 change 中删除仍是迁移必需的 compat 壳

## Decisions

### 1. 残留清理只能发生在前序 change 完成之后

至少以下 change 完成后，才允许进入残留清理实现：

- `refactor-market-data-access`
- `refactor-mobile-ops-transaction-lifecycle`
- `refactor-sim-account-ops-domain`
- `refactor-execution-boundary-runtime`
- `refactor-desktop-app-shell`

### 2. 残留对象必须满足“双条件”才可删除

只有同时满足以下条件，残留对象才可删除：

- 正式替代路径已经落地并通过回归
- 文档主入口已不再指向该残留对象

### 3. 清理顺序按“入口 -> bridge -> helper -> 文档附录 -> 空目录”

这能降低误删仍有真实调用链的对象。

## Risks / Trade-offs

- 清理过早会直接破坏迁移期主工作流
- 清理过晚会继续拖累新需求判断
- 大量删除会让回退难度上升，因此需要显式回退清单

## Migration Plan

1. 先收集残留对象清单
2. 对每个对象标记替代路径与验证项
3. 分批删除并做主工作流回归
4. 最后清理空目录和旧文档入口

## Rollback

- 每一批删除都必须有回退清单
- 关键入口删除前必须可恢复或可切回 compat
