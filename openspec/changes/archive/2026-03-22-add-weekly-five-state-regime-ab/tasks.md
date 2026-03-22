## 1. 合同与配置

- [x] 1.1 定义 `weekly_five_state` regime engine 枚举与配置透传链；DoD：semantic config、runtime config、run_meta 均能区分 `ma200_legacy` 与 `weekly_five_state`；验证：配置 round-trip 测试；风险：engine 名称漂移导致前后端口径不一致
- [x] 1.2 定义 weekly five-state 固定输入合同与周度防抖规则；DoD：状态、原始分数、平滑状态、风险预算都有明确输出；验证：周度样例单测；风险：升级/降级规则实现与设计不一致

## 2. 后端状态机

- [x] 2.1 实现上证指数 `MA120 / slope / ret60 / ret120 / ADX20` 的日频特征计算；DoD：全部特征只使用 trailing 数据；验证：特征单测；风险：ADX 或窗口对齐出错
- [x] 2.2 实现周度观察点打分与五态映射；DoD：周度 raw score 与状态可复现；验证：固定样本断言；风险：观察点取样和映射错误
- [x] 2.3 实现“升级两周确认、降级一周生效”的防抖与日频 forward-fill；DoD：daily 输出中可见 raw/smoothed 状态；验证：状态机单测；风险：防抖引入时间错位

## 3. Router 与风险预算

- [x] 3.1 让 `regime-router` 支持 `weekly_five_state`，且不改个股 breakout + residual 信号逻辑；DoD：非 `DEFENSIVE` 状态仍走主线选股壳；验证：router 回归测试；风险：误接入旧 `TREND_LIGHT` EMA 分支
- [x] 3.2 把五态风险预算接入 `risk-budget-sizing`；DoD：`1.00 / 0.70 / 0.40 / 0.15 / 0.00` 可在 daily 产物中看到；验证：预算单测；风险：预算乘子与原有风控重复叠加

## 4. 前端与产物

- [x] 4.1 更新结果图蒙版与图例以支持五态状态显示；DoD：前端能清楚展示五态阶段；验证：人工截图验收；风险：展示层二次推导状态
- [x] 4.2 更新 regime 配置 UI，仅暴露 engine 选择与 `TURN_WEAK` 风险预算可选项；DoD：UI 保持低自由度；验证：配置加载/保存回归；风险：参数面板继续长胖

## 5. A/B 实验

- [x] 5.1 使用 `baseline_V10.2` 做最小 A/B：`ma200_legacy` vs `weekly_five_state`；DoD：唯一 intended diff 是 regime engine；验证：正式对照页；风险：实验壳被其他配置污染
- [x] 5.2 输出状态分布、交易数、收益、回撤、关键分叉日；DoD：能回答“新状态机是否更适合 40 日突破主线”；验证：对照报告；风险：只看收益不看行为差异
