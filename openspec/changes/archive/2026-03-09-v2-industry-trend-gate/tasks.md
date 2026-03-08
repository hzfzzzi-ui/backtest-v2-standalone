# Tasks: v2-industry-trend-gate

- [x] Implement `compute_sector_rankings()` function: 60d return for 31 sectors, daily cross-sectional rank
- [x] Build stock-to-sector mapping from `pit_security_master` or `SW_L1_INDEX_MAP`
- [x] Build `sector_eligible` matrix (T×N bool) — True if stock's sector is in top 30%
- [x] Integrate sector gate into engine: AND `sector_eligible` with buy signals
- [x] Ensure sector data is loaded via `load_sector_indices()` and passed through pipeline
- [x] Add config params: `enable_sector_gate`, `sector_rank_window`, `sector_top_pct`
- [x] Wire through API (`_experiment_runner_api.py`)
