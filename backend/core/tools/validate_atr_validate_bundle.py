from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate(bundle_dir: Path) -> list[str]:
    errs: list[str] = []
    required = ["bundle_summary.md", "bundle_summary.json"]
    for f in required:
        if not (bundle_dir / f).exists():
            errs.append(f"missing {f}")
    if errs:
        return errs
    try:
        data = json.loads((bundle_dir / "bundle_summary.json").read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return [f"bundle_summary.json unreadable: {exc}"]

    for key, files in [
        ("step1", ["matrix.csv", "effectiveness_report.md", "baseline_ref.json"]),
        ("step2", ["matrix.csv", "wf_matrix.csv", "walkforward_report.md", "baseline_ref.json"]),
        ("step3", ["matrix.csv", "universe_vote.csv", "universe_vote_report.md", "baseline_ref.json"]),
    ]:
        step = data.get(key, {})
        path = Path(str(step.get("results_dir", "")))
        if not path.exists():
            errs.append(f"{key} results dir missing")
            continue
        for f in files:
            if not (path / f).exists():
                errs.append(f"{key} missing {f}")
    return errs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--bundle_dir", required=True)
    args = p.parse_args()
    errs = validate(Path(args.bundle_dir))
    if errs:
        print(errs[0])
        raise SystemExit(1)
    print("OK")


if __name__ == "__main__":
    main()
