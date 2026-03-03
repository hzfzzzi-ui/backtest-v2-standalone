## ADDED Requirements

### Requirement: 批量执行配置目录下所有实验
`batch_runner.py` 接收一个配置目录路径，遍历其中所有 `.json` 文件，依次调用 `run_experiment()` 执行回测。

#### Scenario: 正常批量执行
- **WHEN** 调用 `batch_runner.run_sweep("backend/configs/sweep/")`，目录下有 8 个 JSON 配置
- **THEN** 依次执行 8 个实验，每个实验输出到独立的 `runs/<run_id>/artifacts/` 目录，终端显示进度 `[3/8] r1_rsi_classic_csi800 ...`

#### Scenario: 单个实验失败不阻断后续
- **WHEN** 第 3 个实验因 OOM 或其他异常失败
- **THEN** 记录错误日志，跳过该实验，继续执行第 4~8 个实验，最终汇总报告中标记失败项

#### Scenario: 支持文件名过滤
- **WHEN** 调用 `batch_runner.run_sweep("backend/configs/sweep/", pattern="r1_*")`
- **THEN** 只执行文件名匹配 `r1_*` 的配置文件（第一轮 RSI 扫描）

### Requirement: 实验结果可追溯到配置
每个实验的 `run_meta.json` 必须包含源配置文件名，方便从结果反查参数。

#### Scenario: run_meta 记录来源
- **WHEN** 批量执行完成后查看某个实验的 `run_meta.json`
- **THEN** 包含 `"source_config": "r1_rsi_default_csi800.json"` 字段
