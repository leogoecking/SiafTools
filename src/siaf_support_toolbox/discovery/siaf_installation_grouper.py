from __future__ import annotations

import os
from pathlib import Path

from siaf_support_toolbox.discovery.models import (
    ConnectionReferenceFinding,
    DatabaseCandidate,
    ProcessFinding,
    SiafInstallationFinding,
)


def group_siaf_installations(
    executables: list[Path],
    processes: list[ProcessFinding],
    databases: list[DatabaseCandidate],
    references: list[ConnectionReferenceFinding],
) -> list[SiafInstallationFinding]:
    roots: dict[str, Path] = {}
    executable_paths: dict[str, set[str]] = {}
    for executable in executables:
        resolved = executable.resolve(strict=False)
        root = resolved.parent if resolved.suffix else resolved
        key = _path_key(root)
        roots[key] = root
        executable_paths.setdefault(key, set()).add(str(resolved))

    active_roots = {
        _path_key(Path(item.executable).resolve(strict=False).parent)
        for item in processes
        if item.executable
    }
    databases_by_root: dict[str, set[str]] = {key: set() for key in roots}
    references_by_root: dict[str, set[str]] = {key: set() for key in roots}

    ordered_roots = sorted(roots, key=lambda key: len(str(roots[key])), reverse=True)
    for database in databases:
        owner = _nearest_owner(Path(database.path), ordered_roots, roots)
        if owner is not None:
            databases_by_root[owner].add(database.path)
    for reference in references:
        owner = _nearest_owner(Path(reference.source_file), ordered_roots, roots)
        if owner is not None:
            references_by_root[owner].add(reference.source_file)

    findings = [
        SiafInstallationFinding(
            root=str(root),
            executables=tuple(sorted(executable_paths[key], key=str.casefold)),
            database_paths=tuple(sorted(databases_by_root[key], key=str.casefold)),
            reference_sources=tuple(sorted(references_by_root[key], key=str.casefold)),
            active=key in active_roots,
            confidence=min(
                100,
                (70 if key in active_roots else 40)
                + min(len(databases_by_root[key]), 5) * 5
                + (5 if references_by_root[key] else 0),
            ),
        )
        for key, root in roots.items()
    ]
    return sorted(
        findings,
        key=lambda item: (-int(item.active), -item.confidence, item.root.casefold()),
    )


def installation_for_database(
    database_path: str,
    installations: list[SiafInstallationFinding],
) -> str | None:
    path = Path(database_path)
    owners = [
        item.root
        for item in installations
        if _is_within(path, Path(item.root))
    ]
    return max(owners, key=len, default=None)


def _nearest_owner(
    path: Path,
    ordered_root_keys: list[str],
    roots: dict[str, Path],
) -> str | None:
    return next(
        (key for key in ordered_root_keys if _is_within(path, roots[key])),
        None,
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve(strict=False)))
