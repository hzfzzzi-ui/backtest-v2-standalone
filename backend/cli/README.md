CLI surface roles.

Official surfaces:
- `python -m backend.cli`
- `backend/cli/managed/`
- `backend/scripts/generated/`

Role map:
- `backend/cli/main.py` is the single official command entry.
- `backend/cli/managed/` hosts reusable command implementations invoked by `backend.cli`.
- `backend/scripts/generated/` keeps generated thin study entry scripts only.
- `backend/core/cli/` is compatibility-only and must not receive new command logic.

Rules:
- New command flows belong in `backend/cli/managed/` or `backend/cli/commands/`.
- New studies must use `research/studies/*.study.yaml` plus generated thin scripts.
- Do not treat `backend/core/cli` as a second official CLI surface.
