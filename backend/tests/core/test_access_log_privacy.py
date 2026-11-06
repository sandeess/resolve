import logging

from app.core.logging import DropQueryString, hide_query_strings_in_access_logs


def _record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        __file__,
        1,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1:1", "GET", path, "1.1", 200),
        None,
    )


def test_question_text_in_the_query_string_is_not_logged() -> None:
    record = _record("/journals/j1/ask?q=who+wrote+the+secret+manuscript")
    assert DropQueryString().filter(record)
    line = record.getMessage()
    assert "/journals/j1/ask" in line
    assert "secret" not in line and "?" not in line


def test_paths_without_a_query_are_unchanged() -> None:
    record = _record("/api/v1/me")
    DropQueryString().filter(record)
    assert "/api/v1/me" in record.getMessage()


def test_installing_twice_adds_one_filter() -> None:
    hide_query_strings_in_access_logs()
    hide_query_strings_in_access_logs()
    filters = logging.getLogger("uvicorn.access").filters
    assert sum(isinstance(f, DropQueryString) for f in filters) == 1
