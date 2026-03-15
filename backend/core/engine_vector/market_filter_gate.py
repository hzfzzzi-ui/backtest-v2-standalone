from __future__ import annotations


def resolve_mf_gate_on_today(
    *,
    enable_multifactor_rank: bool,
    mf_rank_gate_mode: str,
    risk_on_today: bool,
    strong_risk_on_today: bool,
    market_state_today: str = "",
) -> bool:
    if not bool(enable_multifactor_rank):
        return False
    mode = str(mf_rank_gate_mode or "ALWAYS_ON").upper()
    market_state = str(market_state_today or "").upper()
    if mode in {"ALWAYS", "ALWAYS_ON"}:
        return True
    if mode in {"ONLY_RISK_ON", "RISK_ON_ONLY"}:
        return bool(risk_on_today)
    if mode in {"STRONG_RISK_ON", "ONLY_STRONG_RISK_ON"}:
        return bool(strong_risk_on_today)
    if mode == "BULL_ONLY":
        return market_state == "BULL"
    if mode == "TRANS_UP_OR_BULL":
        return market_state in {"TRANS_UP", "BULL"}
    return False
