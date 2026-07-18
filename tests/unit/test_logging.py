import logging

from siaf_support_toolbox.core.logging_config import configure_logging, redact_text
from siaf_support_toolbox.core.paths import AppPaths


def test_redacts_common_credential_shapes():
    text = "user=SYSDBA password=masterkey senha:segredo token=abc"
    redacted = redact_text(text)
    assert "masterkey" not in redacted
    assert "segredo" not in redacted
    assert "abc" not in redacted
    assert redacted.count("[REDACTED]") == 3


def test_rotating_log_handler_redacts_formatted_arguments(tmp_path):
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "logs", tmp_path / "exports")
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    for handler in original_handlers:
        root.removeHandler(handler)
    try:
        configure_logging(paths)
        logging.getLogger("security-test").error("password=%s", "secret-value")
        for handler in root.handlers:
            handler.flush()
        content = (paths.logs / "errors.log").read_text(encoding="utf-8")
        assert "secret-value" not in content
        assert "password=[REDACTED]" in content
    finally:
        for handler in list(root.handlers):
            handler.close()
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
