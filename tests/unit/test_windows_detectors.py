from __future__ import annotations

from types import SimpleNamespace

from siaf_support_toolbox.discovery import (
    process_detector,
    registry_detector,
    windows_service_detector,
)
from siaf_support_toolbox.discovery.models import RegistryFinding


def test_process_detector_matches_names_case_insensitively(monkeypatch):
    processes = [
        SimpleNamespace(info={"pid": 10, "name": "SIAFW.EXE", "exe": "C:\\SIAFW.EXE"}),
        SimpleNamespace(info={"pid": 11, "name": "notepad.exe", "exe": "C:\\notepad.exe"}),
    ]
    fake_psutil = SimpleNamespace(
        AccessDenied=PermissionError,
        NoSuchProcess=ProcessLookupError,
        process_iter=lambda _fields: processes,
    )
    monkeypatch.setattr(process_detector, "psutil", fake_psutil)

    findings, issues = process_detector.detect_siaf_processes()

    assert issues == []
    assert len(findings) == 1
    assert findings[0].pid == 10


def test_service_detector_does_not_depend_on_fixed_service_name(monkeypatch):
    def vanished_service():
        raise FileNotFoundError(2, "service disappeared")

    services = [
        SimpleNamespace(
            as_dict=lambda: {
                "name": "CustomDatabaseService",
                "display_name": "ERP Database",
                "description": "Firebird database service",
                "binpath": "C:\\Firebird\\fbserver.exe",
                "status": "running",
            }
        ),
        SimpleNamespace(
            as_dict=lambda: {
                "name": "Spooler",
                "display_name": "Print Spooler",
                "description": "Printer",
                "binpath": "spoolsv.exe",
                "status": "running",
            }
        ),
        SimpleNamespace(as_dict=vanished_service),
    ]
    fake_psutil = SimpleNamespace(
        AccessDenied=PermissionError,
        win_service_iter=lambda: services,
    )
    monkeypatch.setattr(windows_service_detector, "psutil", fake_psutil)
    monkeypatch.setattr(windows_service_detector.sys, "platform", "win32")

    findings, issues = windows_service_detector.detect_firebird_services()

    assert issues == []
    assert len(findings) == 1
    assert findings[0].name == "CustomDatabaseService"


def test_registry_detector_reads_both_views_and_deduplicates(monkeypatch):
    fake_winreg = SimpleNamespace(
        KEY_READ=1,
        KEY_WOW64_32KEY=2,
        KEY_WOW64_64KEY=4,
        HKEY_LOCAL_MACHINE=10,
        HKEY_CURRENT_USER=11,
    )
    finding = RegistryFinding("key", "name", "value", "32-bit")
    monkeypatch.setattr(registry_detector, "winreg", fake_winreg)
    monkeypatch.setattr(registry_detector, "_read_values", lambda *_args: [finding])
    monkeypatch.setattr(registry_detector, "_read_uninstall", lambda *_args: [])

    findings, issues = registry_detector.detect_registry()

    assert issues == []
    assert findings == [finding]
