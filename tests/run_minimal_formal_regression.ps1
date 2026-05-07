$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $repoRoot

try {
    Write-Host "[1/4] pytest tests/unit/test_runtime_boundary_contracts.py"
    python -m pytest tests/unit/test_runtime_boundary_contracts.py

    Write-Host "[2/4] pytest tests/unit/test_research_audit_contract.py::test_evaluate_attribution_traceability_passes_for_unified_combo_governor_snapshot"
    python -m pytest tests/unit/test_research_audit_contract.py::test_evaluate_attribution_traceability_passes_for_unified_combo_governor_snapshot

    Write-Host "[3/4] node --test tests/frontend/test_multi_alpha_workbench.cjs"
    node --test tests/frontend/test_multi_alpha_workbench.cjs

    Write-Host "[4/4] node --test tests/frontend/test_results_workbench_multi_alpha.mjs"
    node --test tests/frontend/test_results_workbench_multi_alpha.mjs

    Write-Host ""
    Write-Host "Minimal formal regression suite completed."
    Write-Host "Manual replay remains separate: replay anchor A_STOCK_ETF_V1 is retained under outputs/replay_anchors."
}
finally {
    Pop-Location
}
