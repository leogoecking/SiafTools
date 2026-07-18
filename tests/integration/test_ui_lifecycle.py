import json
import subprocess
import sys
from pathlib import Path


def test_hidden_ui_navigates_all_pages_and_closes():
    project_root = Path(__file__).resolve().parents[2]
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    completed = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "ui_smoke.py")],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        creationflags=creation_flags,
    )
    result = json.loads(completed.stdout)

    assert len(result["visited"]) == 11
    assert len(set(result["visited"])) == 11
    assert result["closed"] is True
    assert result["dialog_result"] is True
    assert result["preferences_saved"] is True
    assert result["final_theme"] in {"light", "dark"}
