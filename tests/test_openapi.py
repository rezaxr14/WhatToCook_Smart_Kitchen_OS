"""The OpenAPI schema (``/api/schema/``) and Swagger UI (``/api/docs/``) stay complete and CDN-free.

CI additionally runs ``manage.py spectacular --validate --fail-on-warn`` (ci.yml); the strict-validation
test here makes the same check part of ``make test`` so an undocumented view fails locally too.
"""
import json
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RoutePattern

AI_ENDPOINTS = {
    "/api/ai/models/": {"get"},
    "/api/ai/providers/": {"get"},
    "/api/ai/recipe-chat/": {"post"},
    "/api/ai/recipe/{recipe_name}/": {"get"},
    "/api/ai/stream/recipe/": {"get"},
    "/api/ai/suggestions/": {"get", "post"},
    "/api/ai/task-status/{task_id}/": {"get"},
    "/api/pantry/scan-image/": {"post"},
}


def _schema(client):
    response = client.get("/api/schema/", {"format": "json"})
    assert response.status_code == 200, response.status_code
    return json.loads(response.content)


def _documented_routes(patterns=None, prefix=""):
    """Every ``path()`` route under ``api/`` (router-generated regex routes are covered by the validator)."""
    patterns = get_resolver().url_patterns if patterns is None else patterns
    for entry in patterns:
        if isinstance(entry, URLResolver):
            if isinstance(entry.pattern, RoutePattern):
                yield from _documented_routes(entry.url_patterns, prefix + str(entry.pattern))
        elif isinstance(entry, URLPattern) and isinstance(entry.pattern, RoutePattern):
            route = prefix + str(entry.pattern)
            if route.startswith("api/"):
                yield route


class OpenApiSchemaTests(TestCase):
    def test_strict_validation_has_no_warnings_or_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            # --fail-on-warn exits non-zero (SystemExit/CommandError) on any warning or unguessable view
            call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(Path(tmp) / "schema.yml"))

    def test_schema_lists_the_ai_endpoints_with_the_right_methods(self):
        paths = _schema(self.client)["paths"]
        for path, methods in AI_ENDPOINTS.items():
            self.assertIn(path, paths)
            self.assertEqual({m for m in paths[path] if m != "parameters"}, methods, path)

    def test_every_api_route_is_documented(self):
        paths = set(_schema(self.client)["paths"])
        skipped = {"api/schema/", "api/docs/", "api/"}  # "api/" is DRF's router root view, omitted by design
        missing = []
        for route in _documented_routes():
            if route in skipped or "drf_format_suffix" in route:
                continue
            openapi_path = "/" + route.replace("<str:", "{").replace("<int:", "{").replace(">", "}")
            if openapi_path not in paths:
                missing.append(openapi_path)
        self.assertEqual(missing, [], "Add @extend_schema (see GetFood/api_schemas.py) for these routes")

    def test_legacy_server_rendered_aliases_stay_out_of_the_public_docs(self):
        self.assertFalse([p for p in _schema(self.client)["paths"] if p.startswith("/legacy/")])

    def test_ai_request_and_response_shapes_are_described(self):
        schema = _schema(self.client)
        suggestions = schema["paths"]["/api/ai/suggestions/"]["post"]
        body = schema["components"]["schemas"]["SuggestionsRequest"]["properties"]
        self.assertEqual(suggestions["tags"], ["AI"])
        self.assertTrue({"ingredients", "provider", "model", "language", "force_refresh"} <= set(body))
        self.assertIn("text/event-stream", schema["paths"]["/api/ai/stream/recipe/"]["get"]["responses"]["200"]["content"])
        scan = schema["paths"]["/api/pantry/scan-image/"]["post"]
        self.assertEqual({"multipart/form-data", "application/json"}, set(scan["requestBody"]["content"]))
        self.assertTrue({"200", "400", "413"} <= set(scan["responses"]))

    def test_schema_is_served_as_yaml_by_default(self):
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.decode().startswith("openapi:"))


class SwaggerUiTests(TestCase):
    def test_docs_page_loads_assets_locally_not_from_a_cdn(self):
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("/api/schema/", html)
        for cdn in ("cdn.jsdelivr.net", "unpkg.com", "cdnjs.cloudflare.com"):
            self.assertNotIn(cdn, html)
