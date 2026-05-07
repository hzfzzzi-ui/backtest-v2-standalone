from __future__ import annotations

import argparse
from typing import Any

from backend.research import study_loader, study_runner, thin_script


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "study_run",
        help="Run a declarative research study from a .study.yaml definition.",
    )
    parser.add_argument("study", nargs="?", help="Study id like v10/residual_structure_s1 or a direct .study.yaml path.")
    parser.add_argument("--study-path", dest="study_path", help="Explicit path to a .study.yaml file.")
    parser.add_argument("--variant", action="append", dest="variants", default=[], help="Restrict to one or more variant names.")
    parser.add_argument("--window", action="append", dest="windows", default=[], help="Restrict to one or more window keys.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the execution plan without running experiments.")
    parser.add_argument("--emit-thin-script", action="store_true", help="Generate an on-demand thin script under backend/scripts/generated.")
    parser.add_argument("--append-baseline", action="store_true", help="Opt in to compatibility-only baseline append output.")
    parser.add_argument("--skip-baseline-append", action="store_true", help="Do not append study outputs into baseline reports.")
    parser.add_argument("--skip-dual-output", action="store_true", help="Do not write machine/human bundles.")
    parser.set_defaults(handler=_handle)


def _handle(args: argparse.Namespace) -> dict[str, Any]:
    study_ref = args.study_path or args.study
    if not study_ref:
        raise SystemExit("study_run requires either a positional study id/path or --study-path")
    study = study_loader.load_study_definition(study_ref)
    if args.emit_thin_script:
        path = thin_script.write_generated_script(study.study_id)
        return {"study_id": study.study_id, "generated_script": str(path)}
    if args.dry_run:
        return {
            "study": study.as_dict(),
            "plan": study_runner.build_execution_plan(
                study,
                only_variant_names=list(args.variants or []),
                only_window_keys=list(args.windows or []),
            ),
        }
    return study_runner.run_study(
        study,
        only_variant_names=list(args.variants or []),
        only_window_keys=list(args.windows or []),
        write_dual_output=not bool(args.skip_dual_output),
        append_to_baseline=bool(args.append_baseline) and not bool(args.skip_baseline_append),
    )
