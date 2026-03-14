## ADDED Requirements

### Requirement: 正式 PWA 安装必须运行在私有 HTTPS 安全上下文中
系统 MUST 支持在不暴露公网域名的前提下，以私有 HTTPS 域名、私有网络证书或等效安全上下文向手机端提供 PWA 安装能力。系统 SHALL NOT 以公网域名作为默认安装前提。

#### Scenario: 私有 HTTPS 访问移动端
- **WHEN** 用户通过私有 HTTPS 域名访问移动端入口
- **THEN** 系统 SHALL 提供符合 PWA 安装前提的 manifest 与相关前端资源
- **THEN** 该入口 SHALL 继续受私有访问限制约束

#### Scenario: 本机 localhost 开发访问
- **WHEN** 开发者通过 `localhost` 访问移动端
- **THEN** 系统 SHALL 允许本地开发与调试
- **THEN** 开发模式 SHALL NOT 被解释为正式手机部署方案

### Requirement: 非安全上下文的私有 HTTP 只能降级为浏览器模式
当移动端通过非安全上下文的私有 HTTP 访问时，系统 MUST 继续允许浏览器模式使用已有移动看板，但 SHALL NOT 宣称提供完整 PWA 安装能力，也 SHALL NOT 显示误导性的安装提示。

#### Scenario: 局域网 HTTP 打开移动端
- **WHEN** 用户通过 `http://192.168.x.x/...` 访问移动端
- **THEN** 系统 SHALL 正常提供浏览器模式页面
- **THEN** 页面 SHALL 隐藏或禁用仅适用于 PWA 安装的提示与入口

### Requirement: 私有 PWA 入口仍必须禁止公网暴露
系统 MUST 对 PWA 入口、manifest、service worker 相关资源和移动端 API 继续执行私有访问限制。未经显式允许的公网 Host SHALL NOT 获得移动端资源。

#### Scenario: 公网 Host 请求 PWA 资源
- **WHEN** 请求使用公网域名或未允许的 Host 访问移动端入口、manifest 或 service worker
- **THEN** 系统 SHALL 返回拒绝响应
- **THEN** 系统 SHALL NOT 暴露可安装资源或移动端操作接口
