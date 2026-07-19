from __future__ import annotations

import os
import re
from collections import deque
from pathlib import Path

from siaf_support_toolbox.core.constants import DEFAULT_FIREBIRD_PORT
from siaf_support_toolbox.discovery.configuration_reader import read_configuration_text
from siaf_support_toolbox.discovery.models import ConnectionReferenceFinding, DetectionIssue

_CONFIG_SUFFIXES = {".cfg", ".conf", ".ini", ".txt"}
_REMOTE_DSN = re.compile(
    r"(?i)(?P<host>(?![a-z]:)[a-z0-9][a-z0-9_.-]*)"
    r"(?:/(?P<port>\d{1,5}))?:"
    r"(?P<database>(?:[a-z]:[\\/][^\r\n;\"']*?\.fdb)|(?:[a-z0-9_.-]+))"
)
_LOCAL_DATABASE = re.compile(r"(?i)(?P<database>[a-z]:[\\/][^\r\n;\"']*?\.fdb)")
_SENSITIVE_LINE = re.compile(r"(?i)\b(?:password|passwd|senha|pwd|token|secret|csc)\s*[:=]")


def parse_connection_references(
    text: str,
    source_file: str,
) -> list[ConnectionReferenceFinding]:
    findings: list[ConnectionReferenceFinding] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")) or _SENSITIVE_LINE.search(stripped):
            continue
        occupied: list[tuple[int, int]] = []
        for match in _REMOTE_DSN.finditer(stripped):
            port = int(match.group("port") or DEFAULT_FIREBIRD_PORT)
            if not 1 <= port <= 65535:
                continue
            findings.append(
                ConnectionReferenceFinding(
                    match.group("host"),
                    port,
                    match.group("database").strip(),
                    source_file,
                )
            )
            occupied.append(match.span())
        for match in _LOCAL_DATABASE.finditer(stripped):
            if any(start <= match.start() < end for start, end in occupied):
                continue
            findings.append(
                ConnectionReferenceFinding(
                    None,
                    DEFAULT_FIREBIRD_PORT,
                    match.group("database").strip(),
                    source_file,
                )
            )
    unique = {
        (
            (item.host or "").casefold(),
            item.port,
            item.database.casefold(),
            item.source_file.casefold(),
        ): item
        for item in findings
    }
    return list(unique.values())


def detect_siaf_connection_references(
    roots: list[Path],
    *,
    max_depth: int = 2,
    max_directories: int = 200,
    max_files: int = 500,
    max_file_size: int = 1_000_000,
) -> tuple[list[ConnectionReferenceFinding], list[DetectionIssue]]:
    queue = deque((root, 0) for root in roots if root.is_dir())
    visited: set[str] = set()
    inspected_files = 0
    findings: list[ConnectionReferenceFinding] = []
    errors: list[str] = []
    while queue and len(visited) < max_directories and inspected_files < max_files:
        current, depth = queue.popleft()
        normalized = os.path.normcase(str(current.resolve(strict=False)))
        if normalized in visited:
            continue
        visited.add(normalized)
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if inspected_files >= max_files:
                        break
                    try:
                        if depth < max_depth and entry.is_dir(follow_symlinks=False):
                            queue.append((Path(entry.path), depth + 1))
                        elif (
                            entry.is_file(follow_symlinks=False)
                            and Path(entry.name).suffix.casefold() in _CONFIG_SUFFIXES
                            and entry.stat(follow_symlinks=False).st_size <= max_file_size
                        ):
                            inspected_files += 1
                            path = Path(entry.path)
                            text = read_configuration_text(path)
                            findings.extend(parse_connection_references(text, str(path)))
                    except (OSError, UnicodeError) as exc:
                        errors.append(f"{entry.path}: {exc}")
        except OSError as exc:
            errors.append(f"{current}: {exc}")
    issues = (
        [
            DetectionIssue(
                "config_conexao_siaf",
                f"{len(errors)} item(ns) não puderam ser inspecionados",
                "access_denied",
            )
        ]
        if errors
        else []
    )
    return _unique_references(findings), issues


def _unique_references(
    findings: list[ConnectionReferenceFinding],
) -> list[ConnectionReferenceFinding]:
    unique = {
        ((item.host or "").casefold(), item.port, item.database.casefold()): item
        for item in findings
    }
    return sorted(
        unique.values(),
        key=lambda item: ((item.host or "").casefold(), item.port, item.database.casefold()),
    )
