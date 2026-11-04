"""Client for main's calls to the Supabase AI gateway (plan 4.3).

Only this module knows the wire shape of the service-principal route. The
gateway authenticates ``X-Service-Key`` against ``MAIN_SERVICE_KEY`` and meters
the call against the anonymous/registered provider pool; main keeps its own
per-user caps in :mod:`GetFood.ai_guard`.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Iterator

import requests
from django.conf import settings

from .ai_guard import (
    AiDisabled,
    ChallengeRequired,
    PoolExhausted,
    QuotaExceeded,
)

logger = logging.getLogger(__name__)

GATEWAY_PROVIDER_IDS = {"supabase_gateway", "gateway"}


class GatewayError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        retry_after: int | None = None,
        resets_at: str | None = None,
        pool: str | None = None,
        kinds: list[str] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.retry_after = retry_after
        self.resets_at = resets_at
        self.pool = pool
        self.kinds = kinds or []


def gateway_url() -> str:
    return str(getattr(settings, "SUPABASE_GATEWAY_URL", "") or "").strip().rstrip("/")


def gateway_key() -> str:
    return str(getattr(settings, "MAIN_SERVICE_KEY", "") or "").strip()


def gateway_configured() -> bool:
    """A short key would be rejected by the gateway, so treat it as absent."""
    return bool(gateway_url() and len(gateway_key()) >= 32)


def to_api_exception(error: GatewayError):
    """Map a blocking gateway error to main's JSON exception shapes.

    Provider/validation failures return ``None`` so the existing graceful
    fallback (static recipes, local model) still applies.
    """
    if error.code == "challenge_required":
        return ChallengeRequired(error.message, kinds=error.kinds or ["turnstile"])
    if error.code == "ai_pool_exhausted":
        return PoolExhausted(
            error.message,
            pool=error.pool,
            resets_at=error.resets_at,
            retry_after=error.retry_after,
        )
    if error.code == "rate_limited":
        return QuotaExceeded(
            error.message,
            code="rate_limited",
            retry_after=error.retry_after,
            resets_at=error.resets_at,
        )
    if error.code == "quota_exceeded":
        return QuotaExceeded(
            error.message,
            resets_at=error.resets_at,
            retry_after=error.retry_after,
        )
    if error.code in {"ai_disabled", "ai_budget_exhausted"}:
        return AiDisabled(error.message, code=error.code, resets_at=error.resets_at)
    return None


def _headers() -> dict[str, str]:
    return {
        "X-Service-Key": gateway_key(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _timeout() -> float:
    try:
        return float(getattr(settings, "AI_GATEWAY_TIMEOUT", 90))
    except (TypeError, ValueError):
        return 90.0


def _error_from_response(response) -> GatewayError:
    body: dict = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            body = parsed
    except Exception:
        pass

    details = body.get("details") if isinstance(body.get("details"), dict) else {}
    code = str(body.get("code") or body.get("error") or f"http_{response.status_code}")
    message = str(
        body.get("message")
        or body.get("detail")
        or "The AI gateway could not complete the request."
    )
    retry_after = body.get("retry_after")
    try:
        retry_after = int(retry_after) if retry_after is not None else None
    except (TypeError, ValueError):
        retry_after = None
    return GatewayError(
        code,
        message,
        status=response.status_code,
        retry_after=retry_after,
        resets_at=body.get("resets_at"),
        pool=details.get("pool") or body.get("pool"),
        kinds=body.get("kinds") or details.get("kinds"),
    )


def _post(path: str, payload: dict):
    url = f"{gateway_url()}/{path.lstrip('/')}"
    try:
        return requests.post(url, json=payload, headers=_headers(), timeout=_timeout())
    except Exception as exc:
        raise GatewayError("provider_error", f"AI gateway is unreachable: {exc}") from exc


def _post_json(path: str, payload: dict) -> dict:
    response = _post(path, payload)
    if response.status_code >= 400:
        raise _error_from_response(response)
    try:
        data = response.json()
    except Exception as exc:
        raise GatewayError("invalid_model_output", "The AI gateway returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise GatewayError("invalid_model_output", "The AI gateway returned an unexpected payload.")
    return data


def _split_model(model: str | None) -> tuple[str | None, str | None]:
    """Map a picker model id to the gateway's provider/model pair.

    ``openrouter:``/``gemini:`` prefixes are explicit. A namespaced id (anything
    with ``/``) is an OpenRouter model; a ``gemini-`` id goes to Gemini. With no
    model the gateway's own routed default is used.
    """
    raw = str(model or "").strip()
    if not raw:
        return None, None
    lowered = raw.lower()
    if lowered.startswith("openrouter:"):
        return "openrouter", raw.split(":", 1)[1].strip() or None
    if lowered.startswith("gemini:"):
        return "gemini", raw.split(":", 1)[1].strip() or None
    if "/" in raw:
        return "openrouter", raw
    if lowered.startswith("gemini"):
        return "gemini", raw
    return None, raw


def _base_body(
    *,
    mode: str,
    language: str | None,
    model: str | None,
    principal_class: str,
    end_user_ref: str | None,
) -> dict:
    from .ai_service import normalize_language

    body: dict = {
        "mode": mode,
        "locale": normalize_language(language) or "en",
        "principal_class": "registered" if principal_class == "registered" else "anonymous",
    }
    gateway_provider, gateway_model = _split_model(model)
    if gateway_provider:
        body["provider"] = gateway_provider
    if gateway_model:
        body["model"] = gateway_model
    if end_user_ref:
        body["end_user_ref"] = str(end_user_ref)[:128]
    return body


def generate_suggestions(
    ingredients: list[str],
    *,
    model: str | None = None,
    language: str | None = None,
    principal_class: str = "anonymous",
    end_user_ref: str | None = None,
) -> tuple[list[dict], str, list[str]]:
    body = _base_body(
        mode="suggestions",
        language=language,
        model=model,
        principal_class=principal_class,
        end_user_ref=end_user_ref,
    )
    body["ingredients"] = ingredients
    data = _post_json("generate-recipe", body)
    recipes = data.get("recipes") if isinstance(data.get("recipes"), list) else []
    return (
        [item for item in recipes if isinstance(item, dict)],
        str(data.get("model_used") or data.get("model") or model or ""),
        list(data.get("rate_limited_models") or []),
    )


def generate_detail(
    recipe_name: str,
    *,
    model: str | None = None,
    language: str | None = None,
    principal_class: str = "anonymous",
    end_user_ref: str | None = None,
) -> tuple[dict, str, list[str]]:
    body = _base_body(
        mode="detail",
        language=language,
        model=model,
        principal_class=principal_class,
        end_user_ref=end_user_ref,
    )
    body["recipe_name"] = recipe_name
    data = _post_json("generate-recipe", body)
    return (
        data,
        str(data.get("model_used") or data.get("model") or model or ""),
        list(data.get("rate_limited_models") or []),
    )


def generate_chat(
    *,
    recipe_name: str,
    ingredients,
    instructions,
    message: str,
    history: list[dict] | None,
    model: str | None = None,
    language: str | None = None,
    principal_class: str = "anonymous",
    end_user_ref: str | None = None,
) -> dict:
    body = _base_body(
        mode="chat",
        language=language,
        model=model,
        principal_class=principal_class,
        end_user_ref=end_user_ref,
    )
    body.update(
        {
            "recipe_name": recipe_name,
            "message": message,
            "ingredients": ingredients,
            "instructions": instructions,
            "history": (history or [])[-6:],
        }
    )
    data = _post_json("generate-recipe", body)
    return {
        "reply": str(data.get("reply") or ""),
        "model_used": str(data.get("model_used") or data.get("model") or ""),
        "rate_limited_models": list(data.get("rate_limited_models") or []),
        "recipe_name": str(data.get("recipe_name") or recipe_name),
    }


def scan_image(
    image_bytes: bytes,
    mime_type: str,
    *,
    language: str | None = None,
    principal_class: str = "anonymous",
    end_user_ref: str | None = None,
) -> list[dict]:
    from .ai_service import normalize_language

    body = {
        "image": base64.b64encode(image_bytes).decode("ascii"),
        "mime_type": mime_type if mime_type in {"image/jpeg", "image/png", "image/webp"} else "image/jpeg",
        "locale": normalize_language(language) or "en",
        "principal_class": "registered" if principal_class == "registered" else "anonymous",
    }
    if end_user_ref:
        body["end_user_ref"] = str(end_user_ref)[:128]
    data = _post_json("scan-pantry", body)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    return [item for item in items if isinstance(item, dict)]


def stream_recipe(
    recipe_name: str,
    *,
    ingredients: list[str] | None = None,
    model: str | None = None,
    language: str | None = None,
    principal_class: str = "anonymous",
    end_user_ref: str | None = None,
) -> Iterator[str]:
    """Re-emit the gateway's NDJSON deltas as main's SSE chunks."""
    body = _base_body(
        mode="stream",
        language=language,
        model=model,
        principal_class=principal_class,
        end_user_ref=end_user_ref,
    )
    body["recipe_name"] = recipe_name
    body["stream"] = True
    if ingredients:
        body["ingredients"] = ingredients

    response = _post("generate-recipe", body)
    if response.status_code >= 400:
        raise _error_from_response(response)

    try:
        for line in response.iter_lines():
            if not line:
                continue
            try:
                event = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            kind = event.get("type")
            if kind == "delta":
                text = str(event.get("text") or "")
                if text:
                    yield f"data: {json.dumps({'chunk': text, 'done': False})}\n\n"
            elif kind == "final":
                yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                return
            elif kind == "error":
                raise GatewayError(
                    str(event.get("code") or "provider_error"),
                    str(event.get("message") or "The AI gateway stream failed."),
                    retry_after=event.get("retry_after"),
                    resets_at=event.get("resets_at"),
                )
    finally:
        response.close()

    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"


__all__ = [
    "GATEWAY_PROVIDER_IDS",
    "GatewayError",
    "generate_chat",
    "generate_detail",
    "generate_suggestions",
    "gateway_configured",
    "gateway_key",
    "gateway_url",
    "scan_image",
    "stream_recipe",
    "to_api_exception",
]
