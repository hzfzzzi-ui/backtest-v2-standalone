from __future__ import annotations

from backend.core.universe.lineage import get_universe_lineage


def test_hs300_zz500_formal_lineage_points_to_tushare_history_chain() -> None:
    lineage = get_universe_lineage("HS300_ZZ500")

    assert lineage.import_assets[0] == "backend/scripts/fetch_csi800_pit_history.py"
    assert lineage.import_assets[1] == "backend/scripts/build_csi800_formal_history.py"
    assert "fallback/approximate" in lineage.import_assets[3]
    assert "formal history materialization" in lineage.notes


def test_hs300_zz500_csi1000_lineage_documents_union_and_csi1000_audit() -> None:
    lineage = get_universe_lineage("HS300_ZZ500_CSI1000")

    assert lineage.load_table == "pit_index_constituents"
    assert "import_csi800_pit.py" in lineage.import_assets[2]
    assert "import_csi1000_pit.py" in lineage.import_assets[-1]
    assert "000906.SH" in lineage.notes
    assert "000852.SH" in lineage.notes
    assert "refresh sidecar" in lineage.notes
