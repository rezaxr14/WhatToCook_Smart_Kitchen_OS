"""Prometheus /metrics endpoint (django-prometheus), optionally token-protected."""
import hmac

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django_prometheus.exports import ExportToDjangoView


def metrics(request):
    if not settings.METRICS_ENABLED:
        return HttpResponseNotFound()
    token = settings.METRICS_TOKEN
    if token and not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {token}"):
        return HttpResponse("Unauthorized", status=401, headers={"WWW-Authenticate": "Bearer"})
    return ExportToDjangoView(request)
