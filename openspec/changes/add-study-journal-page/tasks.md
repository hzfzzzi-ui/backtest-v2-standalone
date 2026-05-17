## 1. OpenSpec 合同

- [x] 1.1 创建 proposal/design/spec/tasks，明确该功能是 research-only 的研究日志 surface。
- [x] 1.2 运行 `openspec validate add-study-journal-page --strict`，确认 change 合同有效。

## 2. 后端研究日志持久化

- [x] 2.1 新增 `backend/research/study_journal.py`，实现 round JSON 读写、路径防护、列表、详情、新建、更新、追加备注、关联实验。
- [x] 2.2 实现 conclusion registry 扫描，读取 `outputs/studies/conclusions/**/registry.jsonl` 并按 `exp_id/study_id/window/variant` 归一化。
- [x] 2.3 实现确定性 `auto_summary` 生成，输出 headline、conclusion_draft、reliability、facts、risks、next_actions 和 metric_highlights。

## 3. API 与页面入口

- [x] 3.1 新增 `/api/research/study-rounds`、`/api/research/study-rounds/{round_id}`、notes、experiment link、summary refresh API。
- [x] 3.2 新增 `/api/research/study-conclusions` API，用于页面选择证据候选。
- [x] 3.3 在 `backend/main.py` 注册 research router，并提供 `/study-journal` 页面路由。

## 4. 前端研究日志页面

- [x] 4.1 新增 `frontend/study-journal.html`、CSS 和 JS，提供三栏研究日志界面。
- [x] 4.2 页面支持列表加载、轮次详情、新建轮次、追加备注、关联实验、刷新自动总结。
- [x] 4.3 在桌面主入口提供研究日志链接，不改变结果工作台 owner。

## 5. 验证

- [x] 5.1 新增 unit/API 测试，覆盖 round 读写、自动总结、路径越界、API 基本行为。
- [x] 5.2 运行相关 pytest。
- [x] 5.3 启动本地服务，确认 `/study-journal` 可访问。

## 6. 回测工作台集成

- [x] 6.1 在现有回测工作台 rail 增加“研究”入口，并新增 research drawer module。
- [x] 6.2 在主内容区嵌入受控研究日志 iframe，保留 `/study-journal` 独立页面。
- [x] 6.3 切换研究日志工作区时隐藏结果工作台可见区域，切回其他面板时恢复结果工作台 owner。
- [x] 6.4 验证回测页内研究日志可见、独立页面仍可访问、console 无错误。
