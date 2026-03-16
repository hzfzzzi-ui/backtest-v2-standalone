from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def generated_scripts_root() -> Path:
    root = (_repo_root() / "backend" / "scripts" / "generated").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def script_slug(study_id: str) -> str:
    text = str(study_id or "").strip().replace("\\", "/").strip("/")
    if not text:
        raise ValueError("study_id is required")
    return text.replace("/", "_").replace("-", "_")


def generated_script_path(study_id: str) -> Path:
    return generated_scripts_root() / f"run_{script_slug(study_id)}.py"


def render_generated_script(study_id: str) -> str:
    normalized = str(study_id or "").strip().replace("\\", "/").strip("/")
    slug = script_slug(normalized)
    return "\n".join(
        [
            "from __future__ import annotations",
            "",
            "import sys",
            "from pathlib import Path",
            "",
            "REPO_ROOT = Path(__file__).resolve().parents[3]",
            "if str(REPO_ROOT) not in sys.path:",
            "    sys.path.insert(0, str(REPO_ROOT))",
            "",
            "from backend.cli.main import main",
            "",
            "",
            "if __name__ == \"__main__\":",
            f"    raise SystemExit(main([\"study_run\", \"{normalized}\", *(__import__('sys').argv[1:])]))",
            "",
        ]
    )


def write_generated_script(study_id: str) -> Path:
    path = generated_script_path(study_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_generated_script(study_id), encoding="utf-8")
    return path
