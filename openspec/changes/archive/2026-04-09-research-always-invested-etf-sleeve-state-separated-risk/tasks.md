## 1. 研究合同与预算语义
- [x] 1.1 定义 ETF always-on 研究合同  
  DoD：ETF sleeve 各状态尽量保持非零持仓；验证方式：主回放输出状态分层预算 explain；风险：把 ETF 做成第二条股票腿。
- [x] 1.2 定义 `511010.SH / 510300.SH` 的状态分层预算语义  
  DoD：账户层预算能区分 `defense / core_beta`；验证方式：run_meta / audit / query 可见；风险：状态映射过强导致不可归因。

## 2. 执行与可观测性准备
- [x] 2.1 在共享账户执行 runtime 中增加 ETF always-on 风险分层 explain  
  DoD：主 runtime 与前端只讲账户层单一叙事；验证方式：combo_truth / account allocator 面板可见；风险：展示层先行污染研究口径。
- [x] 2.2 保持旧 weak-state patch 为 diagnostics/reference  
  DoD：不新增第二个 owner；验证方式：reason code 与主 runtime owner 一致；风险：双重语义回流。

## 3. 最小 A/B 研究
- [x] 3.1 运行最小 A/B，对比 ETF 非零持仓率、ETF 与个股腿相关性、组合风险收益  
  验证方式：主回放与组合层日度数据对比。
- [x] 3.2 形成研究结论  
  结论：`always_on_v1` 不值得继续推进，已按 no-go 处理并从主代码撤回。

## 4. 结果摘要
- 基线：`exp_20260407_070626665_8e4d`
  - `total_return = 4.835648972383496`
  - `cagr = 0.13755920212270967`
  - `sharpe = 0.48209790913684797`
  - `calmar = 0.4317618802295044`
  - `etf_nonzero_exposure_rate = 0.7635379061371841`
  - `riskoff_etf_nonzero_exposure_rate = 0.5982839313572543`
  - `stock_etf_return_corr = 0.06140174080453021`
  - `stock_etf_return_corr_when_stock_down = 0.03391779754430901`

- always-on 试验：`exp_20260407_071543297_3437`
  - `total_return = 0.7430054678790914`
  - `cagr = 0.04143075701519128`
  - `sharpe = 0.30518224301189606`
  - `calmar = 0.0904371142146462`
  - `etf_nonzero_exposure_rate = 0.9657039711191335`
  - `riskoff_etf_nonzero_exposure_rate = 0.9742589703588144`
  - `stock_etf_return_corr = 0.48833778738321093`
  - `stock_etf_return_corr_when_stock_down = 0.741850295304751`

## 5. 判断
- 这条研究假设虽然提高了 ETF 全程持仓率，但同时显著抬高了 ETF 与股票腿的同向暴露。
- 它没有实现“风险收益错开”，反而把 ETF 重新做成了第二条股票腿。
- 当前正确处理是：保留 change artifacts 与实验结果，撤回主代码实现，不进入主线。
