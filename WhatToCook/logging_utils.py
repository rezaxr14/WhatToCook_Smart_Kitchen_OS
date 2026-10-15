"""Structured logging + request correlation (stdlib only)."""
import contextvars
import json
import logging
import re
import uuid

request_id_var = contextvars.ContextVar("request_id", default="-")
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._\-]{8,64}")


class RequestIDFilter(logging.Filter):
    """Stamp every log record with the current request id."""

    def filter(self, record):
        record.request_id = request_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    """One JSON object per line - what Loki / ELK / CloudWatch expect."""

    def format(self, record):
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class RequestIDMiddleware:
    """Reuse a sane incoming X-Request-ID (e.g. from the ingress) or mint one."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        return response
