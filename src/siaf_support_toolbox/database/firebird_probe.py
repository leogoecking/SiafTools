from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

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


def probe_read_only(
    *,
    dsn: str,
    username: str,
    password: str,
    client_library: str | Path,
    charset: str = "WIN1252",
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

    connection = None
    cursor = None
    try:
        fdb.load_api(str(library_path))
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
            )
        return FirebirdProbeResult(True, current_timestamp, classification)
    except Exception as exc:
        return FirebirdProbeResult(False, None, None, "connection_failed", _translate_error(exc))
    finally:
        if cursor is not None:
            with suppress(Exception):
                cursor.close()
        if connection is not None:
            with suppress(Exception):
                connection.close()


def _translate_error(error: Exception) -> str:
    message = str(error)
    lowered = message.casefold()
    if "winerror 193" in lowered:
        return "A DLL encontrada é incompatível com a arquitetura do aplicativo"
    if "unsupported ods" in lowered:
        return "O cliente/servidor não é compatível com a estrutura da base"
    if "password" in lowered or "login" in lowered:
        return "A credencial autorizada não foi aceita pelo Firebird"
    if "createfile" in lowered or "-902" in lowered:
        return "O caminho detectado não é válido para o serviço Firebird"
    return "Não foi possível validar a conexão Firebird"
