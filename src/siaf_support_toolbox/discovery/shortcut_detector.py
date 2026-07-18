from __future__ import annotations

import os
import subprocess
from collections import deque
from collections.abc import Callable
from pathlib import Path

from siaf_support_toolbox.discovery.models import DetectionIssue, ShortcutFinding

ShortcutResolver = Callable[[Path], tuple[str | None, str | None]]


def default_shortcut_roots() -> list[Path]:
    roots: list[Path] = []
    user_profile = os.environ.get("USERPROFILE")
    public = os.environ.get("PUBLIC")
    app_data = os.environ.get("APPDATA")
    program_data = os.environ.get("PROGRAMDATA")
    if user_profile:
        roots.append(Path(user_profile) / "Desktop")
    if public:
        roots.append(Path(public) / "Desktop")
    if app_data:
        roots.append(Path(app_data) / "Microsoft/Windows/Start Menu/Programs")
    if program_data:
        roots.append(Path(program_data) / "Microsoft/Windows/Start Menu/Programs")
    return [root for root in roots if root.is_dir()]


def detect_siaf_shortcuts(
    roots: list[Path] | None = None,
    *,
    max_depth: int = 4,
    max_directories: int = 500,
    resolver: ShortcutResolver | None = None,
) -> tuple[list[ShortcutFinding], list[DetectionIssue]]:
    queue = deque((root, 0) for root in (roots or default_shortcut_roots()) if root.is_dir())
    visited: set[str] = set()
    matches: list[ShortcutFinding] = []
    scan_errors = 0
    resolution_errors = 0
    resolve = resolver or resolve_windows_shortcut
    while queue and len(visited) < max_directories:
        current, depth = queue.popleft()
        normalized = os.path.normcase(str(current.resolve(strict=False)))
        if normalized in visited:
            continue
        visited.add(normalized)
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        path = Path(entry.path)
                        if path.suffix.casefold() == ".lnk" and "siaf" in path.stem.casefold():
                            try:
                                target_path, working_directory = resolve(path)
                            except (OSError, subprocess.SubprocessError):
                                target_path, working_directory = None, None
                                resolution_errors += 1
                            matches.append(
                                ShortcutFinding(
                                    path=str(path),
                                    target_path=target_path,
                                    working_directory=working_directory,
                                )
                            )
                    elif depth < max_depth and entry.is_dir(follow_symlinks=False):
                        queue.append((Path(entry.path), depth + 1))
        except OSError:
            scan_errors += 1
    issues = []
    if scan_errors:
        issues.append(
            DetectionIssue(
                "atalhos_siaf",
                f"{scan_errors} diretório(s) de atalhos não puderam ser inspecionados",
                "access_denied",
            )
        )
    if resolution_errors:
        issues.append(
            DetectionIssue(
                "atalhos_siaf",
                f"{resolution_errors} atalho(s) não puderam ter o destino resolvido",
                "shortcut_resolution_failed",
            )
        )
    unique = {item.path.casefold(): item for item in matches}
    return sorted(unique.values(), key=lambda item: item.path.casefold()), issues


def resolve_windows_shortcut(path: Path) -> tuple[str | None, str | None]:
    script = (
        "$link=(New-Object -ComObject WScript.Shell).CreateShortcut($env:SIAF_SHORTCUT_PATH);"
        "[Console]::WriteLine($link.TargetPath);"
        "[Console]::WriteLine($link.WorkingDirectory)"
    )
    shortcut_environment = os.environ.copy()
    shortcut_environment["SIAF_SHORTCUT_PATH"] = str(path)
    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        timeout=3,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        env=shortcut_environment,
    )
    if completed.returncode != 0:
        raise OSError(completed.stderr.strip() or "Não foi possível resolver o atalho")
    lines = completed.stdout.splitlines()
    target = lines[0].strip() if lines and lines[0].strip() else None
    working_directory = lines[1].strip() if len(lines) > 1 and lines[1].strip() else None
    return target, working_directory
