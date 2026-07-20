from __future__ import annotations

import os
import re
import socket
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from threading import Lock

from siaf_support_toolbox.discovery.architecture import pe_architecture, process_architecture
from siaf_support_toolbox.discovery.schema_classifier import (
    DatabaseType,
    SchemaClassification,
    classify_schema,
)


@dataclass(frozen=True, slots=True)
class FirebirdProbeResult:
    success: bool
    current_timestamp: str | None
    classification: SchemaClassification | None
    error_code: str | None = None
    message: str | None = None
    server_version: str | None = None
    ods_version: str | None = None


_API_LOAD_LOCK = Lock()
_SUPPORTED_FIREBIRD_VERSION = re.compile(r"(?<!\d)2\.5\.7(?:\.\d+)?(?!\d)")
_SUPPORTED_ODS_VERSION = re.compile(r"(?<!\d)11\.2(?!\d)")


def probe_read_only(
    *,
    dsn: str,
    username: str,
    password: str,
    client_library: str | Path,
    charset: str = "WIN1252",
    host: str | None = None,
    port: int | None = None,
    connect_timeout: float = 3.0,
) -> FirebirdProbeResult:
    """Abre uma conexão temporária read-only; a credencial nunca é persistida ou registrada."""
    library_path = Path(client_library)
    if pe_architecture(library_path) != process_architecture():
        return FirebirdProbeResult(
            False,
            None,
            None,
            "architecture_mismatch",
            "A DLL Firebird é incompatível com a arquitetura do aplicativo",
        )

    try:
        import fdb
    except ImportError:
        return FirebirdProbeResult(False, None, None, "dependency_missing", "fdb não instalado")

    if host and port and not _port_reachable(host, port, connect_timeout):
        return FirebirdProbeResult(
            False,
            None,
            None,
            "port_unavailable",
            "Não foi possível alcançar automaticamente o serviço Firebird",
        )

    connection = None
    cursor = None
    try:
        loaded_library = load_api_library(fdb, library_path)
        if loaded_library is not None:
            return FirebirdProbeResult(
                False,
                None,
                None,
                "client_library_already_loaded",
                (
                    "Outra DLL Firebird já está carregada nesta sessão. "
                    "Reinicie o aplicativo para trocar a biblioteca cliente"
                ),
            )
        connection = fdb.connect(dsn=dsn, user=username, password=password, charset=charset)
        read_only_tpb = getattr(fdb, "ISOLATION_LEVEL_READ_COMMITED_RO", None)
        if read_only_tpb is None:
            connection.close()
            return FirebirdProbeResult(
                False,
                None,
                None,
                "readonly_unavailable",
                "O driver não expõe o modo de transação somente leitura esperado",
            )
        connection.begin(tpb=read_only_tpb)
        cursor = connection.cursor()
        server_version = _string_attribute(connection, "version") or _string_attribute(
            connection, "engine_version"
        )
        ods_version = _string_attribute(connection, "ods")
        cursor.execute("SELECT CURRENT_TIMESTAMP FROM RDB$DATABASE")
        current_timestamp = str(cursor.fetchone()[0])
        cursor.execute(
            "SELECT TRIM(RDB$RELATION_NAME) FROM RDB$RELATIONS "
            "WHERE COALESCE(RDB$SYSTEM_FLAG, 0) = 0"
        )
        tables: list[str] = []
        while True:
            batch = cursor.fetchmany(200)
            if not batch:
                break
            tables.extend(str(row[0]).strip() for row in batch)
        classification = classify_schema(tables)
        connection.rollback()
        if not classification.is_accepted:
            if classification.database_type == DatabaseType.AMBIGUOUS:
                code = "ambiguous_schema"
                message = "A estrutura da base é ambígua e não permite classificá-la com segurança"
            elif classification.database_type == DatabaseType.NOT_SIAF:
                code = "not_siaf"
                message = "O arquivo abriu, mas não contém as tabelas esperadas do SIAF"
            else:
                code = "low_schema_confidence"
                message = "A base possui poucos indícios para ser aceita como uma base SIAF"
            return FirebirdProbeResult(
                False,
                current_timestamp,
                classification,
                code,
                message,
                server_version,
                ods_version,
            )
        compatibility_issue = runtime_compatibility_issue(server_version, ods_version)
        if compatibility_issue is not None:
            code, message = compatibility_issue
            return FirebirdProbeResult(
                False,
                current_timestamp,
                classification,
                code,
                message,
                server_version,
                ods_version,
            )
        return FirebirdProbeResult(
            True,
            current_timestamp,
            classification,
            server_version=server_version,
            ods_version=ods_version,
        )
    except Exception as exc:
        return FirebirdProbeResult(
            False, None, None, "connection_failed", translate_connection_error(exc)
        )
    finally:
        if cursor is not None:
            with suppress(Exception):
                cursor.close()
        if connection is not None:
            with suppress(Exception):
                connection.close()


def translate_connection_error(error: Exception) -> str:
    message = str(error)
    lowered = message.casefold()
    if "winerror 193" in lowered:
        return "A DLL encontrada é incompatível com a arquitetura do aplicativo"
    if "unsupported ods" in lowered:
        return "O cliente/servidor não é compatível com a estrutura da base"
    if "password" in lowered or "login" in lowered:
        return "A credencial autorizada não foi aceita pelo Firebird"
    if any(
        marker in lowered
        for marker in ("connection refused", "timed out", "unreachable", "connection reset")
    ):
        return "Não foi possível alcançar automaticamente o serviço Firebird"
    if "createfile" in lowered:
        return "O caminho detectado não é válido para o serviço Firebird"
    return "Não foi possível validar a conexão Firebird"


def _port_reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=max(0.1, timeout)):
            return True
    except OSError:
        return False


def _string_attribute(value: object, name: str) -> str | None:
    attribute = getattr(value, name, None)
    return str(attribute) if attribute not in (None, "") else None


def runtime_compatibility_issue(
    server_version: str | None,
    ods_version: str | None,
) -> tuple[str, str] | None:
    if not server_version:
        return (
            "firebird_version_unconfirmed",
            "A versão do servidor Firebird não pôde ser confirmada",
        )
    if not _SUPPORTED_FIREBIRD_VERSION.search(server_version):
        return (
            "unsupported_firebird_version",
            "Apenas Firebird 2.5.7 é aceito nesta versão da ferramenta",
        )
    if not ods_version:
        return ("ods_version_unconfirmed", "A versão ODS da base não pôde ser confirmada")
    if not _SUPPORTED_ODS_VERSION.search(ods_version):
        return (
            "unsupported_ods_version",
            "A base não utiliza a estrutura ODS 11.2 esperada para Firebird 2.5",
        )
    return None


def load_api_library(fdb_module: object, requested_path: Path) -> str | None:
    with _API_LOAD_LOCK:
        api = fdb_module.load_api(str(requested_path))  # type: ignore[attr-defined]
    loaded_path = getattr(api, "client_library_name", None)
    if not loaded_path or _same_library(requested_path, str(loaded_path)):
        return None
    return str(loaded_path)


def _same_library(requested_path: Path, loaded_path: str) -> bool:
    requested = os.path.normcase(str(requested_path.resolve(strict=False)))
    loaded = Path(loaded_path)
    if loaded.is_absolute():
        return requested == os.path.normcase(str(loaded.resolve(strict=False)))
    return os.path.normcase(requested_path.name) == os.path.normcase(loaded.name)


# Compatibilidade interna para diagnósticos e testes das fases anteriores.
_translate_error = translate_connection_error
_load_api_library = load_api_library
