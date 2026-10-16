"""Request/response shapes for the OpenAPI schema (``/api/schema/``, ``/api/docs/``).

These serializers are **documentation only**: the function-based views build their JSON by hand and
never instantiate them. They exist so ``drf-spectacular`` can describe each endpoint; keep them in
sync with the view they annotate (``tests/test_openapi.py`` guards that every route is documented).
"""
from rest_framework import serializers

from .serializers import UserPantrySerializer, UserSerializer

PROVIDER_HELP = "AI backend: `gemini` (cloud), `lmstudio` (local) or empty for the server default."
LANGUAGE_HELP = "Preferred response language code (e.g. `en`, `fa`, `es`, `ar`, `tr`); unsupported values fall back to English."


# --------------------------------------------------------------------------- shared
class ErrorSerializer(serializers.Serializer):
    error = serializers.CharField()


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()


class StatsSerializer(serializers.Serializer):
    total_recipes = serializers.IntegerField()
    total_ingredients = serializers.IntegerField()
    total_users = serializers.IntegerField()


class HealthChecksSerializer(serializers.Serializer):
    database = serializers.ChoiceField(choices=["ok", "down"])
    cache = serializers.ChoiceField(choices=["ok", "degraded", "down"])
    broker = serializers.ChoiceField(choices=["ok", "degraded", "skipped"])


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "error"])
    checks = HealthChecksSerializer()


# --------------------------------------------------------------------------- auth
class LoginRequestSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})


class SignupRequestSerializer(LoginRequestSerializer):
    email = serializers.EmailField(required=False, allow_blank=True)


class AuthResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user = UserSerializer()
    pantry = UserPantrySerializer()


class MeResponseSerializer(serializers.Serializer):
    authenticated = serializers.BooleanField()
    user = UserSerializer(allow_null=True)
    pantry = UserPantrySerializer(allow_null=True)


# --------------------------------------------------------------------------- pantry
class PantryAddRequestSerializer(serializers.Serializer):
    ingredient_id = serializers.IntegerField(required=False)
    ingredient_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    name = serializers.CharField(required=False, help_text="Free-text ingredient; created if it does not exist yet.")


class PantryRemoveRequestSerializer(serializers.Serializer):
    ingredient_id = serializers.IntegerField()


class PantryMutationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    pantry = UserPantrySerializer()


class ScanRequestSerializer(serializers.Serializer):
    image = serializers.FileField(required=False, help_text="Photo upload (multipart). JPEG/PNG/WEBP, max 8 MB by default.")
    image_base64 = serializers.CharField(required=False, help_text="Alternative to `image`: base64 or a `data:image/...;base64,` URL.")
    auto_add = serializers.BooleanField(required=False, default=False, help_text="Add detected items to the pantry.")
    provider = serializers.CharField(required=False, help_text=PROVIDER_HELP)
    language = serializers.CharField(required=False, help_text=LANGUAGE_HELP)


class DetectedIngredientSerializer(serializers.Serializer):
    name = serializers.CharField()
    category = serializers.CharField()
    confidence = serializers.FloatField()
    estimated_quantity = serializers.CharField(required=False)
    display_name = serializers.CharField(required=False, help_text="Localised name when `language` was requested.")


class ScanResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    detected_count = serializers.IntegerField()
    detected_ingredients = DetectedIngredientSerializer(many=True)
    auto_added = serializers.BooleanField()
    added_ingredients = serializers.ListField(child=serializers.CharField())
    pantry = UserPantrySerializer(allow_null=True)


class CanCookResponseSerializer(serializers.Serializer):
    full_matches = serializers.ListField(child=serializers.DictField(), help_text="Recipes whose ingredients are all in the pantry.")
    partial_matches = serializers.ListField(child=serializers.DictField(), help_text="Recipes with some ingredients missing.")
    pantry_ingredient_count = serializers.IntegerField()
    total_full_matches = serializers.IntegerField()
    total_partial_matches = serializers.IntegerField()


# --------------------------------------------------------------------------- AI
class AiProviderSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=["gemini", "lmstudio"])
    name = serializers.CharField()
    active = serializers.BooleanField()
    online = serializers.BooleanField()
    badge = serializers.CharField()


class AiProvidersResponseSerializer(serializers.Serializer):
    default_provider = serializers.CharField()
    has_gemini = serializers.BooleanField()
    gemini_model = serializers.CharField()
    has_lmstudio = serializers.BooleanField()
    lmstudio_online = serializers.BooleanField()
    lmstudio_model = serializers.CharField()
    lmstudio_error = serializers.CharField(allow_null=True, required=False)
    providers = AiProviderSerializer(many=True)


class AiModelSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField(required=False)
    description = serializers.CharField(required=False)


class AiModelsResponseSerializer(serializers.Serializer):
    models = AiModelSerializer(many=True)
    current_model = serializers.CharField()
    is_live = serializers.BooleanField(help_text="False when the curated list is served instead of Google's live model list.")


class SuggestionsRequestSerializer(serializers.Serializer):
    ingredients = serializers.ListField(child=serializers.CharField(), required=False,
                                        help_text="Defaults to the caller's pantry (or the demo pantry for guests).")
    provider = serializers.CharField(required=False, help_text=PROVIDER_HELP)
    model = serializers.CharField(required=False, help_text="Specific model id; falls back through the model list on quota errors.")
    language = serializers.CharField(required=False, help_text=LANGUAGE_HELP)
    force_refresh = serializers.BooleanField(required=False, default=False, help_text="Bypass the Redis/DB suggestion cache.")


class SuggestionsResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["done", "processing"], help_text="`processing` means poll `/api/ai/task/{task_id}/`.")
    recipes = serializers.ListField(child=serializers.DictField(), required=False)
    task_id = serializers.CharField(required=False)
    cached = serializers.BooleanField(required=False)
    provider = serializers.CharField(required=False)
    model = serializers.CharField(required=False, allow_null=True)
    model_used = serializers.CharField(required=False)
    rate_limited_models = serializers.ListField(child=serializers.CharField(), required=False)


class TaskStatusResponseSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["pending", "done", "error"])
    recipes = serializers.ListField(child=serializers.DictField(), required=False)
    error = serializers.CharField(required=False)


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["user", "assistant"])
    content = serializers.CharField()


class RecipeChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    recipe_name = serializers.CharField(required=False)
    ingredients = serializers.ListField(child=serializers.JSONField(), required=False)
    instructions = serializers.CharField(required=False)
    history = ChatMessageSerializer(many=True, required=False, help_text="Only the last six turns are used.")
    provider = serializers.CharField(required=False, help_text=PROVIDER_HELP)
    model = serializers.CharField(required=False)
    language = serializers.CharField(required=False, help_text=LANGUAGE_HELP)


class RecipeChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    model_used = serializers.CharField()
    rate_limited_models = serializers.ListField(child=serializers.CharField())
    recipe_name = serializers.CharField()


# --------------------------------------------------------------------------- shopping list
class ShoppingItemSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    category = serializers.CharField()
    quantity = serializers.CharField()
    checked = serializers.BooleanField()
    added_from = serializers.CharField(allow_blank=True)


class ShoppingItemInputSerializer(serializers.Serializer):
    name = serializers.CharField()
    category = serializers.CharField(required=False)
    quantity = serializers.CharField(required=False)
    checked = serializers.BooleanField(required=False)
    added_from = serializers.CharField(required=False)


class ShoppingListResponseSerializer(serializers.Serializer):
    items = ShoppingItemSerializer(many=True)
    count = serializers.IntegerField()


class ShoppingAddRequestSerializer(ShoppingItemInputSerializer):
    name = serializers.CharField(required=False, help_text="Single-item form; or send `items` for several at once.")
    items = ShoppingItemInputSerializer(many=True, required=False)


class ShoppingAddResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    added_count = serializers.IntegerField()
    items = ShoppingItemSerializer(many=True)


class ShoppingSyncRequestSerializer(serializers.Serializer):
    items = ShoppingItemInputSerializer(many=True)


class ShoppingSyncResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class ShoppingUpdateRequestSerializer(serializers.Serializer):
    checked = serializers.BooleanField(required=False)
    name = serializers.CharField(required=False)
    quantity = serializers.CharField(required=False)
    category = serializers.CharField(required=False)


class ShoppingUpdateResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    id = serializers.IntegerField()
    checked = serializers.BooleanField()


class ShoppingRemoveResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    id = serializers.IntegerField()


class ShoppingClearRequestSerializer(serializers.Serializer):
    only_completed = serializers.BooleanField(required=False, default=False, help_text="Only remove checked-off items.")


class ShoppingClearResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    deleted_count = serializers.IntegerField()


# --------------------------------------------------------------------------- telegram
class TelegramLinkResponseSerializer(serializers.Serializer):
    auth_token = serializers.CharField()
    is_connected = serializers.BooleanField()
    telegram_username = serializers.CharField(allow_null=True)
    bot_username = serializers.CharField()
    connect_url = serializers.CharField()
    direct_tg_url = serializers.CharField()
    web_tg_url = serializers.CharField()


class TelegramWebhookResponseSerializer(serializers.Serializer):
    status = serializers.CharField(help_text="e.g. `connected`, `ignored`, `unlinked`, `pantry_viewed`, `recipes_suggested`.")
    user = serializers.CharField(required=False)


# --------------------------------------------------------------------------- schema generation hook
def exclude_legacy_routes(endpoints, **kwargs):
    """drf-spectacular preprocessing hook: keep the server-rendered ``/legacy/`` aliases out of the public docs."""
    return [e for e in endpoints if not e[0].startswith("/legacy/")]
