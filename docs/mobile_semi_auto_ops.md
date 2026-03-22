# 移动端半自动交易运行说明

## 边界

- 手机端只负责查看建议、二次确认、撤回和查看执行状态。
- 桌面端保留最终执行权，负责消费 `approval_tickets/` 并回写 `execution_events/`。
- 手机端不得直连券商，也不得绕过桌面执行器直接修改真实持仓。

## 运行产物

移动端相关运行产物统一落在 `outputs/mobile_ops/`：

- `approval_tickets/`
  - 手机端确认后的待执行单。
- `execution_events/`
  - 桌面执行器回写的 append-only 执行事件流。
- `daily_briefings/`
  - 开盘前待办、执行异常、收盘后复盘摘要。
- `notifications/`
  - 私有通知 feed，当前只启用站内提醒。
- `audit_log.jsonl`
  - 逐笔审计日志。

## 当前状态机

- 确认前：
  - `approval_cards`
- 待执行：
  - `approved_pending`
- 执行中：
  - `claimed`
  - `submitted`
  - `partially_filled`
- 终态：
  - `filled`
  - `cancelled`
  - `rejected`
  - `revoked`
  - `expired`

## 桌面执行器职责

桌面执行器当前按文件协议工作：

1. 轮询 `outputs/mobile_ops/approval_tickets/`
2. 领取 `approved_pending` ticket
3. 回写 `claimed / submitted / partially_filled / filled ...`
4. 将异常写入 `execution_events/` 和 `audit_log.jsonl`

如果桌面执行器不可用，手机端不会自动执行，只会看到：

- 待执行单积压
- 执行超时
- 交易机器人页的异常/降级提示

## 私有访问与 PWA

### 允许访问的正式前提

- 私网 Host
- Tailscale / CGNAT 私网地址
- `localhost` 仅用于本机开发

### 当前受私网限制的资源

- `/mobile`
- `/mobile.html`
- `/api/mobile/*`
- `/assets/manifest.webmanifest`
- `/mobile-service-worker.js`
- 移动端专用 CSS / JS / 图标资源

### 浏览器模式与 PWA 模式

- 私有 HTTP：
  - 允许浏览器模式访问
  - 不承诺完整安装能力
  - 当前提醒降级为站内提醒
- 私有 HTTPS：
  - 允许 manifest + service worker
  - 可作为正式 PWA 安装上下文

## 通知降级

当前首个私有通知通道是 `in_app_feed`。

- 默认行为：
  - 待办、执行异常、收盘复盘都汇总到 dashboard 内的站内提醒
- 降级行为：
  - 如果首选通道不是 `in_app_feed`，但当前未接入对应发送器，系统会明确降级回 `in_app_feed`
  - 浏览器模式下也只提供站内提醒，不假装已经提供系统推送

## 回退

需要回退时，按下面顺序关闭：

1. 关闭手机端确认入口
2. 停止桌面执行器消费 `approval_tickets/`
3. 停止读取 `execution_events/`
4. 移除 `daily_briefings/` 和 `notifications/` 聚合
5. 关闭 `/mobile-service-worker.js` 与 manifest 暴露

只读移动看板与桌面研究平台可以独立保留。
