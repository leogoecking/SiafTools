import logging

import pytest

from siaf_support_toolbox.core.logging_config import configure_logging, redact_text
from siaf_support_toolbox.core.paths import AppPaths


@pytest.fixture
def isolated_root_logger():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    for handler in original_handlers:
        root.removeHandler(handler)
    try:
        yield root
    finally:
        for handler in list(root.handlers):
            handler.close()
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
        root.setLevel(original_level)


@pytest.mark.parametrize(
    ("text", "secrets"),
    [
        ("user=SYSDBA password=masterkey senha:segredo token=abc", ["masterkey", "segredo", "abc"]),
        ("{'password': 'two words', 'token': 'structured'}", ["two words", "structured"]),
        ('password="quoted value" pwd:plain-value', ["quoted value", "plain-value"]),
    ],
)
def test_redacts_common_credential_shapes(text, secrets):
    redacted = redact_text(text)
    assert all(secret not in redacted for secret in secrets)
    assert redacted.count("[REDACTED]") == len(secrets)


def test_redacts_entire_quoted_value_with_escaped_quote():
    redacted = redact_text(r"""{"password": "first\"leaked-tail"}""")

    assert redacted == '{"password": [REDACTED]}'
    assert "leaked-tail" not in redacted


def test_rotating_log_handler_redacts_formatted_arguments(tmp_path, isolated_root_logger):
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "logs", tmp_path / "exports")
    configure_logging(paths)
    logging.getLogger("security-test").error("password=%s", "secret-value")
    for handler in isolated_root_logger.handlers:
        handler.flush()
    content = (paths.logs / "errors.log").read_text(encoding="utf-8")
    assert "secret-value" not in content
    assert "password=[REDACTED]" in content


def test_log_formatter_redacts_credentials_from_traceback(tmp_path, isolated_root_logger):
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "logs", tmp_path / "exports")
    configure_logging(paths)

    try:
        raise RuntimeError("password=traceback-secret")
    except RuntimeError:
        logging.getLogger("security-test").exception("detector failed")

    for handler in isolated_root_logger.handlers:
        handler.flush()
    content = (paths.logs / "errors.log").read_text(encoding="utf-8")
    assert "traceback-secret" not in content
    assert "password=[REDACTED]" in content


def test_logging_configuration_is_idempotent(tmp_path, isolated_root_logger):
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "logs", tmp_path / "exports")

    configure_logging(paths)
    configure_logging(paths)

    roles = [getattr(handler, "_siaf_role", None) for handler in isolated_root_logger.handlers]
    assert roles.count("app") == 1
    assert roles.count("errors") == 1


def test_logging_reconfiguration_moves_handlers_to_new_paths(tmp_path, isolated_root_logger):
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first = AppPaths(
        first_root,
        first_root / "data",
        first_root / "logs",
        first_root / "exports",
    )
    second = AppPaths(
        second_root,
        second_root / "data",
        second_root / "logs",
        second_root / "exports",
    )

    configure_logging(first)
    returned = configure_logging(second)
    logging.getLogger("reconfiguration-test").info("new-destination-marker")
    for handler in isolated_root_logger.handlers:
        handler.flush()

    assert returned == second.logs
    assert "new-destination-marker" in (second.logs / "app.log").read_text(encoding="utf-8")
    assert "new-destination-marker" not in (first.logs / "app.log").read_text(encoding="utf-8")


def test_app_log_rotates_when_size_limit_is_reached(tmp_path, isolated_root_logger):
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "logs", tmp_path / "exports")
    configure_logging(paths)
    app_handler = next(
        handler
        for handler in isolated_root_logger.handlers
        if getattr(handler, "_siaf_role", None) == "app"
    )
    app_handler.maxBytes = 256

    logger = logging.getLogger("rotation-test")
    for index in range(20):
        logger.info("rotation-line-%02d %s", index, "x" * 80)
    app_handler.flush()

    assert (paths.logs / "app.log").is_file()
    assert (paths.logs / "app.log.1").is_file()
