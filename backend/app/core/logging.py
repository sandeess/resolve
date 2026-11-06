"""Keeps request content out of access logs.

The Ask page puts the question in its address (`/journals/<id>/ask?q=...`) so it can
be shared and bookmarked. A page load or reload therefore reaches the server with
that text in the URL, and uvicorn's access log would record it. This filter drops
the query string from access-log lines so logs hold paths, status codes and timings
but never question text.
"""

import logging


class DropQueryString(logging.Filter):
    """Rewrites uvicorn access records so `/path?query` is logged as `/path`."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access args: (client_addr, method, full_path, http_version, status)
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


def hide_query_strings_in_access_logs() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, DropQueryString) for f in logger.filters):
        logger.addFilter(DropQueryString())
