"""Adaptive AI challenge and per-identity daily caps (plan 4.1-4.2).

The Supabase gateway owns the provider-wide pools. This module is main's
counterpart: the same "verify once, then every N provider-bound calls" rule and
the anonymous/registered daily request caps, kept in Django's cache so a
single web process is not the limit.

Cache-backed counters are intentionally best-effort: if Redis is unavailable the
gateway still protects the provider. A cache outage therefore fails open here
rather than taking every AI endpoint down.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)

DEMO_USERNAME = "ChefDemo"

# How long a challenge/cap counter is kept. Daily caps include the date in the
# key; the challenge counter only resets on verification.
COUNTER_TIMEOUT_SECONDS = 30 * 24 * 60 * 60

CHALLENGE_KINDS = ("turnstile",)


class AiError(APIException):
    """APIException carrying a stable machine-readable code and extra fields."""

    status_code = 500
    default_detail = "The AI service is unavailable."
    error_code = "ai_error"

    def __init__(self, detail: str | None = None, *, code: str | None = None, **extra):
        self.error_code = code or self.error_code
        self.extra = extra
        super().__init__(detail or self.default_detail, self.error_code)


class ChallengeRequired(AiError):
    status_code = 403
    default_detail = "Verify that you are human to keep using AI."
    error_code = "challenge_required"

    def __init__(self, detail: str | None = None, **extra):
        extra.setdefault("kinds", list(CHALLENGE_KINDS))
        super().__init__(detail, **extra)


class QuotaExceeded(AiError):
    status_code = 429
    default_detail = "You have reached the AI limit. Try again tomorrow."
    error_code = "quota_exceeded"


class PoolExhausted(QuotaExceeded):
    status_code = 429
    default_detail = "Today's demo capacity is reached. Sign in or try again tomorrow."
    error_code = "ai_pool_exhausted"


class AiDisabled(AiError):
    status_code = 503
    default_detail = "AI features are temporarily unavailable."
    error_code = "ai_disabled"


class ProviderUnavailable(AiError):
    status_code = 502
    default_detail = "The AI provider could not answer. Please try again."
    error_code = "provider_error"


def turnstile_enabled() -> bool:
    return bool(str(getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip())


def turnstile_site_key() -> str:
    return str(getattr(settings, "TURNSTILE_SITE_KEY", "") or "").strip()


def challenge_every_n() -> int:
    try:
        return max(1, int(getattr(settings, "AI_CHALLENGE_EVERY_N", 3)))
    except (TypeError, ValueError):
        return 3


def client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> tuple[bool, str | None]:
    """Validate a Turnstile token server-side.

    Returns ``(ok, reason)``. A missing secret or transport failure is reported
    as a failure; callers decide whether the gate is enabled at all.
    """
    secret = str(getattr(settings, "TURNSTILE_SECRET_KEY", "") or "").strip()
    if not secret:
        return False, "not_configured"
    if not token:
        return False, "missing_token"

    payload = {"secret": secret, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    url = getattr(
        settings,
        "TURNSTILE_SITEVERIFY_URL",
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    )
    try:
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # transport/JSON failure means "not verified"
        logger.warning("Turnstile verification failed: %s", exc)
        return False, "verification_unavailable"

    if not data.get("success"):
        return False, "failed"

    expected_action = str(getattr(settings, "TURNSTILE_ACTION", "") or "").strip()
    reported_action = str(data.get("action") or "").strip()
    if expected_action and reported_action and reported_action != expected_action:
        return False, "action_mismatch"

    allowed = getattr(settings, "TURNSTILE_ALLOWED_HOSTNAMES", None) or []
    hostname = str(data.get("hostname") or "").strip()
    if allowed and hostname not in allowed:
        return False, "hostname_mismatch"

    return True, None


def _ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
        request.session.modified = True
    return request.session.session_key


def is_registered(request) -> bool:
    user = getattr(request, "user", None)
    return bool(
        user is not None
        and user.is_authenticated
        and user.get_username() != DEMO_USERNAME
    )


def challenge_identity(request) -> str:
    """Stable per-person key: account id, or the session for demo/anonymous.

    The shared ``ChefDemo`` account is deliberately keyed by session so one
    visitor cannot exhaust the demo challenge for everyone else.
    """
    if is_registered(request):
        return f"u{request.user.pk}"
    return f"s{_ensure_session_key(request)}"


def _challenge_key(identity: str) -> str:
    return f"wtc:ai:challenge:{identity}"


def reset_challenge(request) -> None:
    """Mark the caller as verified (a sign-in or a step-up success)."""
    if not turnstile_enabled():
        return
    try:
        cache.set(_challenge_key(challenge_identity(request)), 0, COUNTER_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("Could not reset the AI challenge counter: %s", exc)


def _daily_limit(request, kind: str) -> int:
    registered = is_registered(request)
    if kind == "scan":
        name = "AI_USER_DAILY_SCAN" if registered else "AI_ANON_DAILY_SCAN"
        default = 15 if registered else 5
    else:
        name = "AI_USER_DAILY_AI" if registered else "AI_ANON_DAILY_AI"
        default = 60 if registered else 20
    try:
        return max(0, int(getattr(settings, name, default)))
    except (TypeError, ValueError):
        return default


def _resets_at() -> str:
    tomorrow = timezone.localdate() + timedelta(days=1)
    midnight = timezone.make_aware(datetime.combine(tomorrow, time.min))
    return midnight.isoformat()


def _daily_key(identity: str, kind: str) -> str:
    return f"wtc:ai:daily:{kind}:{identity}:{timezone.localdate().isoformat()}"


def _read_counter(key: str) -> int:
    try:
        value = cache.get(key)
    except Exception as exc:
        logger.warning("AI counter read failed: %s", exc)
        return 0
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _write_counter(key: str, value: int) -> None:
    try:
        cache.set(key, value, COUNTER_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("AI counter write failed: %s", exc)


def begin_ai_call(request, kind: str = "ai") -> None:
    """Account for one provider-bound AI call, or raise before it is made.

    Cache hits must not call this. The order is deliberate: a capped request
    does not consume a challenge slot, and a challenged request does not consume
    the daily allowance.
    """
    if kind not in {"ai", "scan"}:
        kind = "ai"

    identity = challenge_identity(request)

    limit = _daily_limit(request, kind)
    used = _read_counter(_daily_key(identity, kind))
    if used >= limit:
        plan = "free" if is_registered(request) else "anonymous"
        raise QuotaExceeded(
            f"You have reached today's {limit} {'scans' if kind == 'scan' else 'AI requests'} "
            "for this plan. Try again tomorrow.",
            code="quota_exceeded",
            limit=limit,
            kind=kind,
            plan=plan,
            resets_at=_resets_at(),
        )

    if turnstile_enabled():
        every_n = challenge_every_n()
        state = _read_counter(_challenge_key(identity))
        if state >= every_n:
            raise ChallengeRequired(reason="adaptive")
        _write_counter(_challenge_key(identity), state + 1)

    _write_counter(_daily_key(identity, kind), used + 1)


def challenge_state(request) -> int:
    """Exposed for tests and diagnostics."""
    return _read_counter(_challenge_key(challenge_identity(request)))
