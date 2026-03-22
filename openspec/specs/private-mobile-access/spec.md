# private-mobile-access Specification

## Purpose
TBD - created by archiving change add-mobile-signal-dashboard. Update Purpose after archive.
## Requirements
### Requirement: 手机端入口必须默认限制在私有访问域内
系统 MUST 对手机端页面和手机端 API 执行 Host 访问限制。除本机地址、私网 IP、CGNAT 私网地址或显式配置的允许主机外，系统 MUST 拒绝访问 `/mobile` 及 `/api/mobile/*`。

#### Scenario: 局域网地址访问手机页
- **WHEN** 用户通过 `http://192.168.x.x:port/mobile` 或其他允许的私有主机访问手机端入口
- **THEN** 系统 SHALL 允许请求进入后续登录流程

#### Scenario: 公网域名访问手机页
- **WHEN** 请求使用公网域名或未显式允许的公网 Host 访问 `/mobile`
- **THEN** 系统 SHALL 返回拒绝响应
- **THEN** 系统 SHALL NOT 暴露手机端页面内容

### Requirement: 手机端必须要求口令登录后才能读取看板数据
系统 MUST 为手机端提供基于口令的登录能力。未登录请求 SHALL NOT 读取手机看板数据，已登录请求 SHALL 通过带有效期的会话凭证访问受保护接口。

#### Scenario: 正确口令登录
- **WHEN** 用户提交正确的手机端访问口令
- **THEN** 系统 SHALL 签发有效会话凭证
- **THEN** 后续同会话请求 SHALL 可以访问手机看板接口

#### Scenario: 错误口令登录
- **WHEN** 用户提交错误口令
- **THEN** 系统 SHALL 返回认证失败
- **THEN** 系统 SHALL NOT 签发会话凭证

#### Scenario: 会话过期后访问受保护接口
- **WHEN** 用户持有过期或无效的会话凭证请求 `/api/mobile/*`
- **THEN** 系统 SHALL 返回未认证响应

### Requirement: 手机端认证状态必须可校验与主动退出
系统 MUST 提供手机端会话状态检查与退出接口，便于页面刷新后恢复登录状态，并允许用户主动清除当前会话。

#### Scenario: 页面刷新后校验登录状态
- **WHEN** 手机端页面加载或刷新时请求会话状态接口
- **THEN** 系统 SHALL 返回当前会话是否有效

#### Scenario: 主动退出登录
- **WHEN** 用户请求退出登录
- **THEN** 系统 SHALL 清除当前会话凭证
- **THEN** 后续请求 SHALL 重新要求登录

