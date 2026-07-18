from __future__ import annotations

import os
from collections import deque
from collections.abc import Iterable
from pathlib import Path


def find_exact_names(
    roots: Iterable[str | Path],
    names: set[str] | frozenset[str],
    *,
    max_depth: int = 3,
    max_directories: int = 750,
) -> tuple[list[Path], list[str]]:
    """Busca nomes exatos em raízes fundamentadas, com limites globais explícitos."""
    targets = {name.casefold() for name in names}
    queue: deque[tuple[Path, int]] = deque()
    visited: set[str] = set()
    matches: list[Path] = []
    errors: list[str] = []

    for root in roots:
        path = Path(root)
        if path.is_dir():
            queue.append((path, 0))

    while queue and len(visited) < max_directories:
        current, depth = queue.popleft()
        normalized = os.path.normcase(str(current.resolve(strict=False)))
        if normalized in visited:
            continue
        visited.add(normalized)
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if (
                            entry.is_file(follow_symlinks=False)
                            and entry.name.casefold() in targets
                        ):
                            matches.append(Path(entry.path))
                        elif depth < max_depth and entry.is_dir(follow_symlinks=False):
                            queue.append((Path(entry.path), depth + 1))
                    except OSError as exc:
                        errors.append(f"{entry.path}: {exc}")
        except OSError as exc:
            errors.append(f"{current}: {exc}")

    unique = {os.path.normcase(str(path.resolve(strict=False))): path for path in matches}
    return sorted(unique.values(), key=lambda item: str(item).casefold()), errors
