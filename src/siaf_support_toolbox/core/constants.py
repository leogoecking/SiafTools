from __future__ import annotations

SIAF_EXECUTABLE_NAMES = frozenset({"siafw.exe"})
SIAF_DATABASE_NAMES = frozenset({"siafw.fdb", "siafloja.fdb"})
FIREBIRD_PROCESS_NAMES = frozenset(
    {
        "fbserver.exe",
        "fbguard.exe",
        "fb_inet_server.exe",
        "firebird.exe",
        "ibserver.exe",
        "ibguard.exe",
    }
)
FIREBIRD_CLIENT_NAMES = frozenset({"fbclient.dll", "gds32.dll"})
DEFAULT_FIREBIRD_PORT = 3050
MINIMUM_SCHEMA_CONFIDENCE = 50

SIAFLOJA_SIGNATURE = frozenset(
    {"DSIAF006", "DSIAF010", "DSIAF011", "DSIAF036", "DSIAF037", "DSIAF400", "DSIAF401"}
)
SIAFW_SIGNATURE = frozenset(
    {"DSIAF001", "DSIAF050", "DSIAF051", "DSIAF052", "DSIAF053", "DSIAF095"}
)
