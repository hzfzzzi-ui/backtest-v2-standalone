# Weekly Reports Archive

本目录用于持久化保存每周投资周报，供后续复盘时读取历史基线。

当前初始化内容：

- `US_AI_Bubble/2026-W19_US_AI_Bubble.md`
- `CN_Ashare/2026-W19_CN_Ashare_Theme.md`
- `weekly_report_index.csv`
- `weekly_report_index.jsonl`

## 目录约定

```text
docs/weekly_reports/
├─ weekly_report_index.csv
├─ weekly_report_index.jsonl
├─ US_AI_Bubble/
│  └─ 2026-W19_US_AI_Bubble.md
└─ CN_Ashare/
   └─ 2026-W19_CN_Ashare_Theme.md
```

## 后续规则

每次生成新周报后：

1. 把全文保存为 Markdown。
2. 把文末“历史索引块”追加到 `weekly_report_index.csv` 或 `weekly_report_index.jsonl`。
3. 下次分析时先读取最近 4-8 周索引，再比较市场状态、风险评分、主题退潮判断、触发条件和行动建议。

## 数据质量说明

这些周报是投资研究过程记录，不是交易指令。自动任务生成的周报在交易前仍应重新联网核验关键数据、公告、休市安排和价格口径。
