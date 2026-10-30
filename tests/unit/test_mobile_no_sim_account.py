from pathlib import Path


def test_mobile_shell_does_not_advertise_removed_simulation_cash_pool():
    root = Path(__file__).resolve().parents[2] / "frontend"
    html = (root / "mobile.html").read_text(encoding="utf-8")
    script = (root / "assets/js/mobile-dashboard.js").read_text(encoding="utf-8")
    worker = (root / "mobile-service-worker.js").read_text(encoding="utf-8")

    assert "mdDepositBtn" not in html
    assert "/api/mobile/cash-pool/" not in script
    assert "handleDeposit" not in script
    assert "mobile-dashboard.js?v=20261030_nosim01" in html
    assert "mobile-dashboard.js?v=20261030_nosim01" in worker
    assert "mobile-dashboard.css?v=20261030_nosim01" in html
    assert "mobile-dashboard.css?v=20261030_nosim01" in worker
