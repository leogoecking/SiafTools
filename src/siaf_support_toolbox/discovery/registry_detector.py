from __future__ import annotations

import sys

from siaf_support_toolbox.discovery.models import DetectionIssue, RegistryFinding

if sys.platform == "win32":
    import winreg
else:  # pragma: no cover
    winreg = None  # type: ignore[assignment]

_DIRECT_KEYS = (
    r"SOFTWARE\Firebird Project\Firebird Server\Instances",
    r"SOFTWARE\Borland\InterBase",
)
_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"


def _read_values(root: int, key_path: str, access: int, view: str) -> list[RegistryFinding]:
    assert winreg is not None
    findings: list[RegistryFinding] = []
    with winreg.OpenKey(root, key_path, 0, access) as key:
        value_count = winreg.QueryInfoKey(key)[1]
        for index in range(value_count):
            name, value, _ = winreg.EnumValue(key, index)
            findings.append(RegistryFinding(key_path, name or "(padrão)", str(value), view))
    return findings


def _read_uninstall(root: int, access: int, view: str) -> list[RegistryFinding]:
    assert winreg is not None
    findings: list[RegistryFinding] = []
    with winreg.OpenKey(root, _UNINSTALL_KEY, 0, access) as parent:
        subkey_count = winreg.QueryInfoKey(parent)[0]
        for index in range(subkey_count):
            subkey_name = winreg.EnumKey(parent, index)
            try:
                with winreg.OpenKey(parent, subkey_name) as subkey:
                    values: dict[str, str] = {}
                    for value_index in range(winreg.QueryInfoKey(subkey)[1]):
                        name, value, _ = winreg.EnumValue(subkey, value_index)
                        values[name] = str(value)
                    searchable = " ".join(
                        values.get(name, "") for name in ("DisplayName", "Publisher")
                    ).casefold()
                    if any(term in searchable for term in ("firebird", "interbase", "siaf")):
                        full_key = f"{_UNINSTALL_KEY}\\{subkey_name}"
                        for name in ("DisplayName", "DisplayVersion", "InstallLocation"):
                            if values.get(name):
                                findings.append(RegistryFinding(full_key, name, values[name], view))
            except OSError:
                continue
    return findings


def detect_registry() -> tuple[list[RegistryFinding], list[DetectionIssue]]:
    detector = "registro_windows"
    if winreg is None:
        return [], [
            DetectionIssue(detector, "Detector disponível somente no Windows", "unsupported")
        ]

    findings: list[RegistryFinding] = []
    issues: list[DetectionIssue] = []
    views = (
        (winreg.KEY_READ | winreg.KEY_WOW64_32KEY, "32-bit"),
        (winreg.KEY_READ | winreg.KEY_WOW64_64KEY, "64-bit"),
    )
    for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for access, view in views:
            for key_path in _DIRECT_KEYS:
                try:
                    findings.extend(_read_values(root, key_path, access, view))
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    issues.append(DetectionIssue(detector, f"{key_path} ({view}): {exc}"))
            try:
                findings.extend(_read_uninstall(root, access, view))
            except FileNotFoundError:
                continue
            except OSError as exc:
                issues.append(DetectionIssue(detector, f"uninstall ({view}): {exc}"))

    unique = {(item.key, item.name, item.value, item.view): item for item in findings}
    return list(unique.values()), issues
