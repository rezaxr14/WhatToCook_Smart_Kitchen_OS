"""Request-language helpers for the ``display_*`` serializer fields.

The canonical model fields (``name``, ``description``, ``instructions``) stay
English on purpose: matching, Telegram and the tests compare against them.
Translations live beside them and are only used for display.
"""

from __future__ import annotations

from django.conf import settings


def normalize_language(value: str | None) -> str | None:
    if not value:
        return None
    base = value.strip().lower().split("-")[0].split("_")[0]
    supported = getattr(settings, "SUPPORTED_CONTENT_LANGUAGES", ("en",))
    return base if base in supported else None


def request_language(request) -> str:
    """First supported language from ``Accept-Language`` (q-values ignored)."""
    if request is None:
        return getattr(settings, "DEFAULT_CONTENT_LANGUAGE", "en")
    header = request.headers.get("Accept-Language", "")
    for part in header.split(","):
        language = normalize_language(part.split(";")[0])
        if language:
            return language
    return getattr(settings, "DEFAULT_CONTENT_LANGUAGE", "en")


def translated(value, language: str, fallback: str = "") -> str:
    """Pick a translation for ``language``; English/blank falls back."""
    if language == "en":
        return fallback
    if isinstance(value, dict):
        candidate = value.get(language)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return fallback
