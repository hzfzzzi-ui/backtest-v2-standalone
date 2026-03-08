## ADDED Requirements

### Requirement: 公开单次回测入口必须统一路由到 stage pipeline shell
系统 SHALL 让公开单次回测入口在完成配置编译与数据装载后统一进入 stage pipeline shell。

#### Scenario: API run 路由统一
- **WHEN** 前端或外部调用公开单次回测 API
- **THEN** 请求 SHALL 经由 `config_json -> compiler -> DataBundle -> stage pipeline shell`

#### Scenario: 脚本入口路由统一
- **WHEN** 仓库内受支持的单次回测脚本调用主运行入口
- **THEN** 脚本 SHALL 进入同一条 stage pipeline shell 路径

### Requirement: legacy 编排层只允许作为适配层存在
在 stage pipeline shell 上线后，legacy orchestrator SHALL 只承担 adapter 或执行核职责，不得继续充当第二条公开运行主线。

#### Scenario: 保留 legacy 计算核
- **WHEN** stage pipeline shell 需要复用已有 fill / NAV / 交易记录逻辑
- **THEN** 系统 MAY 通过 adapter 调用 legacy 计算核
- **THEN** legacy 计算核 SHALL NOT 作为公开入口直接暴露给调用方

#### Scenario: 基线门禁后才能继续删除旧编排
- **WHEN** 系统用 stage pipeline shell 替换了任一 legacy 编排职责
- **THEN** 核心回测产物对锁定基线的比较 SHALL 通过既定门禁后，才允许继续删除下一层 legacy 编排
