from __future__ import annotations

import argparse

from backend.core.config.loader import load_config
from backend.core.config.validate import validate_config
from backend.core.tools.bundles import run_bundle
from backend.core.tools.experiment_runner import run_experiment


def main() -> None:
    parser = argparse.ArgumentParser(description="backtest_v2 CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate-config", help="validate config")
    p_val.add_argument("--config", required=True)

    p_exp = sub.add_parser("experiment", help="run experiment preset")
    p_exp.add_argument("--config", required=True)
    p_exp.add_argument("--preset", default="G1-G4")
    p_exp.add_argument("--symbols", default="")

    p_bundle = sub.add_parser("bundle", help="run bundle workflow")
    p_bundle.add_argument("--config", required=True)
    p_bundle.add_argument("--bundle", required=True)
    p_bundle.add_argument("--symbols", default="")
    p_bundle.add_argument("--start_date", default="")
    p_bundle.add_argument("--end_date", default="")

    args = parser.parse_args()

    if args.cmd == "validate-config":
        cfg, cfg_hash = load_config(args.config)
        validate_config(cfg)
        print("config ok")
        print(f"config_hash={cfg_hash}")
        return

    if args.cmd == "experiment":
        overrides = {}
        if args.symbols:
            overrides["symbols"] = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
        result = run_experiment(args.config, args.preset, overrides)
        print(f"exp_id={result['exp_id']}")
        print(f"results_dir={result['results_dir']}")
        return

    if args.cmd == "bundle":
        overrides = {}
        if args.symbols:
            overrides["symbols"] = [s.strip() for s in str(args.symbols).split(",") if s.strip()]
        if args.start_date:
            overrides["start_date"] = args.start_date
        if args.end_date:
            overrides["end_date"] = args.end_date
        result = run_bundle(args.bundle, args.config, overrides)
        print(f"bundle_dir={result['bundle_dir']}")
        return


if __name__ == "__main__":
    main()
