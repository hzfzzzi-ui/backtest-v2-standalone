## ADDED Requirements

### Requirement: 新桌面壳正式接管默认宿主入口
系统 SHALL 让新的单页 `desktop app` 成为桌面端默认宿主入口，并通过单一 root mount 接管页面可见主结构。

#### Scenario: 默认宿主入口指向新桌面壳
- **WHEN** 用户打开桌面端首页
- **THEN** 系统 MUST 通过新桌面壳而不是旧主 bootstrap 挂载主界面

### Requirement: 旧桌面壳只允许作为迁移层
系统 SHALL 将旧 `backtest_v2.js`、旧 bridge 和旧桌面 page controls 定义为迁移层，并为其设置正式退出条件。

#### Scenario: 旧壳不再是正式主路径
- **WHEN** 系统描述桌面端正式主路径
- **THEN** 旧壳组件 MUST 不再被定义为正式主入口
