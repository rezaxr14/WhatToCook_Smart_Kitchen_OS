"""
Production rate limiting for the WhatToCook API.

Design
------
Every endpoint gets an explicit throttle *scope*: a named bucket whose rate
comes from ``REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`` (baseline table in
``GetFood/rate_limits.py``; overridable per deployment with the
``THROTTLE_RATES`` env var, e.g. ``THROTTLE_RATES="ai=10/min;signup=4/hour"``).

Buckets are keyed by:
  * the authenticated user id when a session exists, or
  * the client IP address for anonymous traffic.

Logged-in users therefore get their own quota instead of sharing an IP-wide
bucket, while anonymous abuse (bots, scrapers) is capped per IP.

The custom exception handler converts a throttled response into a consistent
JSON shape and attaches a ``Retry-After`` header so clients can back off:

    HTTP 429
    {
      "error": "rate_limited",
      "detail": "Rate limit exceeded. Try again in 42s.",
      "retry_after": 42
    }
"""

from __future__ import annotations

from django.conf import settings as dj_settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import Throttled
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import exception_handler as drf_exception_handler


class WtcScopeThrottle(SimpleRateThrottle):
    """Rate bucket with a fixed ``scope``, keyed per user (auth'd) or IP.

    Rates are resolved from ``settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']``
    at instantiation time (per request) instead of being captured at class
    definition, so runtime env overrides and ``override_settings`` tests both
    work reliably.
    """

    scope = "catalog"

    def get_rate(self):
        # Kill switch (THROTTLING_ENABLED=false): load tests and local debugging. DRF treats a rate of None as
        # "never throttle". It must not be done by emptying the rate table: that makes every scope an error below.
        if not getattr(dj_settings, "THROTTLING_ENABLED", True):
            return None
        rates = dj_settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        if not self.scope:
            raise ImproperlyConfigured("Throttle scope is not set.")
        try:
            return rates[self.scope]
        except KeyError:
            raise ImproperlyConfigured(f"No default throttle rate set for '{self.scope}' scope") from None

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = f"u{request.user.pk}"
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


def _throttle_class(scope: str) -> type[WtcScopeThrottle]:
    return type(
        f"WtcThrottle{scope.replace('_', ' ').title().replace(' ', '')}",
        (WtcScopeThrottle,),
        {"scope": scope},
    )


def scoped(scope: str, scope2: str | None = None):
    """Attach throttle scope(s) to a function-based view.

    Usage:

        @api_view(["POST"])
        @scoped("auth", "auth_daily")
        def api_auth_login(request): ...

    Two scopes => two independent buckets that must BOTH pass
    (e.g. 15/min AND 150/day).
    """

    def decorator(view_func):
        classes = [_throttle_class(scope)]
        if scope2:
            classes.append(_throttle_class(scope2))
        view_func.throttle_classes = classes
        return view_func

    return decorator


# ---------------------------------------------------------------------------
# Consistent 429 responses (JSON + Retry-After)
# ---------------------------------------------------------------------------


def wtc_exception_handler(exc, context):
    """DRF exception handler: keep defaults, but shape 429s nicely."""
    if isinstance(exc, Throttled):
        wait = max(1, int(getattr(exc, "wait", None) or 1))
        detail = (
            f"Rate limit exceeded for this action. "
            f"Please slow down and try again in {wait}s."
        )
        response = Response(
            {
                "error": "rate_limited",
                "detail": detail,
                "retry_after": wait,
            },
            status=429,
        )
        response["Retry-After"] = str(wait)
        return response

    return drf_exception_handler(exc, context)
