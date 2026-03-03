## 1. 报告修正 (report.js)

- [x] 1.1 从"信号策略"子表移除 ATR 窗口和 ATR 倍数行（report.js:192-201，删除 atrN/atrK 变量及对应 `<tr>` 行）
- [x] 1.2 持仓分析子表中"个股上限触发"和"行业上限触发"显示 `未实现` 而非 `iNum(0)`（report.js:156-157）
- [x] 1.3 复合信号子表标题追加 `(未实现)` 标注（report.js:291）

## 2. 前端控件标注 TBD — 选股范围 (index.html)

- [x] 2.1 成交额 label 改为 `成交额 ≥ (20日均额) <span style="color:#999">(TBD)</span>`（index.html:131）
- [x] 2.2 行业范围 label 改为 `行业范围 <span style="color:#999">(TBD)</span>`（index.html:137）
- [x] 2.3 涨跌停规则 label 改为 `涨跌停规则 <span style="color:#999">(TBD)</span>`（index.html:205）
- [x] 2.4 成分口径 label 改为 `成分口径 <span style="color:#999">(TBD)</span>`（index.html:216）
- [x] 2.5 行业体系 — "自定义 (占位)" option 文字改为 `自定义 (TBD)`（index.html:230）
- [x] 2.6 价格范围 label 改为 `价格范围 <span style="color:#999">(TBD)</span>`（index.html:244）
- [x] 2.7 成交价假设 label 改为 `成交价假设 <span style="color:#999">(仅 next_open)</span>`（index.html:185）

## 3. 前端控件标注 TBD — 信号生成 (index.html)

- [x] 3.1 入场趋势过滤标题追加 TBD：`入场趋势过滤 <span style="color:#999">(TBD)</span>`（index.html:334）
- [x] 3.2 Composition Pipeline summary 改为 `Composition Pipeline <span style="color:#999">(TBD)</span>`（index.html:372）
- [x] 3.3 Live Preview summary 改为 `Live Preview <span style="color:#999">(TBD)</span>`（index.html:387）

## 4. 前端控件标注 TBD — 仓位风控 (index.html)

- [x] 4.1 单票上限 label 改为 `单票上限% <span style="color:#999">(TBD)</span>`（index.html:460）
- [x] 4.2 行业上限 label 改为 `行业上限% <span style="color:#999">(TBD)</span>`（index.html:461）
- [x] 4.3 现金不足策略的"缩量" option 文字改为 `缩量 (TBD)`（index.html:463）

## 5. 缓存版本号更新

- [x] 5.1 更新 index.html 中 report.js 的缓存版本号（确保浏览器加载最新报告逻辑）
