# backend/scripts/ops

这个目录是运维/审计/一次性分析脚本目录，不是正式主实现目录。

约束：

- 不在这里沉淀 baseline 主逻辑、runtime 主逻辑、研究主真相
- 不直接从脚本里 `import PostgresDataProvider`
- 需要数据库访问时，只能走 `backend.core.data.provider_factory`
- 输出只落到 `outputs/ops/`，不反向定义源码真相

如果一个分析需要长期复用，应优先迁到：

- `backend/research`
- `backend/core/tools`
- `backend/core/audit`

这里保留的是运维脚本和历史分析入口，不应继续扩成主链。
