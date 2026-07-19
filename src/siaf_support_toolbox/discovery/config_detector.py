from __future__ import annotations

import re
from pathlib import Path

from siaf_support_toolbox.core.constants import DEFAULT_FIREBIRD_PORT
from siaf_support_toolbox.discovery.bounded_scan import find_exact_names
from siaf_support_toolbox.discovery.configuration_reader import read_configuration_text
from siaf_support_toolbox.discovery.models import (
    AliasFinding,
    DetectionIssue,
    FirebirdConfigurationFinding,
)

_PORT_PATTERN = re.compile(r"^\s*RemoteServicePort\s*=\s*(\d+)\s*$", re.IGNORECASE)


def parse_aliases(text: str, source_file: str = "aliases.conf") -> list[AliasFinding]:
    findings: list[AliasFinding] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")) or "=" not in stripped:
            continue
        alias, database = (part.strip() for part in stripped.split("=", 1))
        if alias and database:
            findings.append(AliasFinding(alias, database.strip('"'), source_file))
    return findings


def parse_firebird_port(text: str) -> int:
    for line in text.splitlines():
        if line.lstrip().startswith(("#", ";")):
            continue
        match = _PORT_PATTERN.match(line)
        if match:
            port = int(match.group(1))
            if 1 <= port <= 65535:
                return port
    return DEFAULT_FIREBIRD_PORT


def detect_firebird_configurations(
    roots: list[Path],
) -> tuple[list[FirebirdConfigurationFinding], list[DetectionIssue]]:
    issues: list[DetectionIssue] = []
    matches, scan_errors = find_exact_names(
        roots, {"aliases.conf", "firebird.conf"}, max_depth=2, max_directories=300
    )
    grouped: dict[str, dict[str, object]] = {}
    for path in matches:
        try:
            text = read_configuration_text(path)
            root = str(path.parent.resolve(strict=False))
            group = grouped.setdefault(
                root,
                {
                    "port": DEFAULT_FIREBIRD_PORT,
                    "config_file": None,
                    "aliases": [],
                },
            )
            if path.name.casefold() == "aliases.conf":
                aliases = group["aliases"]
                assert isinstance(aliases, list)
                aliases.extend(parse_aliases(text, str(path)))
            else:
                group["port"] = parse_firebird_port(text)
                group["config_file"] = str(path)
        except (OSError, UnicodeError) as exc:
            issues.append(DetectionIssue("config_firebird", f"{path}: {exc}"))
    if scan_errors:
        issues.append(
            DetectionIssue(
                "config_firebird",
                f"{len(scan_errors)} diretório(s) não puderam ser inspecionados",
                "access_denied",
            )
        )
    findings = [
        FirebirdConfigurationFinding(
            root=root,
            port=int(data["port"]),
            config_file=str(data["config_file"]) if data["config_file"] else None,
            aliases=tuple(data["aliases"]),
        )
        for root, data in sorted(grouped.items())
    ]
    return findings, issues
