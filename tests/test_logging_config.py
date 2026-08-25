import json
import logging
from app.logging_config import JsonFormatter, configure_logging


def test_json_formatter_basic_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="x.py",
        lineno=1,
        msg="hello world",
        args=(),
        exc_info=None,
    )
    line = formatter.format(record)
    payload = json.loads(line)

    assert payload["level"] == "INFO"
    assert payload["logger"] == "test.logger"
    assert payload["message"] == "hello world"
    assert "ts" in payload
    assert payload["ts"].endswith("+00:00") or "T" in payload["ts"]


def test_json_formatter_includes_extra_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="voice-agent",
        level=logging.INFO,
        pathname="main.py",
        lineno=10,
        msg="Job started",
        args=(),
        exc_info=None,
    )
    record.room = "lab-call-abc"
    record.llm_prompt_tokens = 42

    payload = json.loads(formatter.format(record))
    assert payload["room"] == "lab-call-abc"
    assert payload["llm_prompt_tokens"] == 42


def test_json_formatter_handles_exception():
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="x.py",
            lineno=1,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    payload = json.loads(formatter.format(record))
    assert payload["message"] == "failed"
    assert "exception" in payload
    assert "ValueError" in payload["exception"]
    assert "boom" in payload["exception"]


def test_configure_logging_sets_json_handler(capsys):
    configure_logging("INFO")
    log = logging.getLogger("test.configure")
    log.info("structured", extra={"room": "r1"})

    captured = capsys.readouterr()
    lines = [ln for ln in captured.out.splitlines() if ln.strip()]
    assert lines
    payload = json.loads(lines[-1])
    assert payload["message"] == "structured"
    assert payload["room"] == "r1"