from __future__ import annotations

from pathlib import Path

from siaf_support_toolbox.core.constants import SIAF_DATABASE_NAMES
from siaf_support_toolbox.discovery.bounded_scan import find_exact_names
from siaf_support_toolbox.discovery.models import (
    DatabaseCandidate,
    DetectionIssue,
    Evidence,
)


def locate_databases(
    roots: list[Path],
    siaf_installations: list[Path],
    explicit_paths: list[Path] | None = None,
) -> tuple[list[DatabaseCandidate], list[DetectionIssue]]:
    matches, scan_errors = find_exact_names(roots, SIAF_DATABASE_NAMES, max_depth=4)
    explicit = [
        path
        for path in (explicit_paths or [])
        if path.name.casefold() in SIAF_DATABASE_NAMES and path.is_file()
    ]
    unique_matches = {
        str(path.resolve(strict=False)).casefold(): path for path in matches + explicit
    }
    matches = list(unique_matches.values())
    install_directories = {
        item.parent.resolve(strict=False) if item.is_file() else item.resolve(strict=False)
        for item in siaf_installations
    }
    findings: list[DatabaseCandidate] = []
    for path in matches:
        name = path.name.casefold()
        evidence = [Evidence("nome_esperado", path.name, 20)]
        score = 20
        if any(path.resolve(strict=False) == item.resolve(strict=False) for item in explicit):
            score += 30
            evidence.append(Evidence("configuracao_firebird", str(path), 30))
        resolved_parent = path.parent.resolve(strict=False)
        if any(_is_near(resolved_parent, install) for install in install_directories):
            score += 25
            evidence.append(Evidence("proximidade_instalacao_siaf", str(path.parent), 25))
        try:
            size = path.stat().st_size
            if size > 0:
                score += 5
                evidence.append(Evidence("arquivo_nao_vazio", str(size), 5))
        except OSError:
            size = None
        findings.append(
            DatabaseCandidate(
                path=str(path),
                kind_hint="SIAFW" if name == "siafw.fdb" else "SIAFLOJA",
                size_bytes=size,
                score=min(score, 100),
                evidence=tuple(evidence),
            )
        )

    issues: list[DetectionIssue] = []
    if scan_errors:
        issues.append(
            DetectionIssue(
                "localizador_bases",
                f"{len(scan_errors)} diretório(s) não puderam ser inspecionados",
                "access_denied",
            )
        )
    return sorted(findings, key=lambda item: (-item.score, item.path.casefold())), issues


def _is_near(path: Path, installation: Path) -> bool:
    try:
        path.relative_to(installation)
        return True
    except ValueError:
        pass
    try:
        installation.relative_to(path)
        return True
    except ValueError:
        return path.parent == installation.parent
