import hashlib
import logging
import os
import requests
from datetime import timedelta

logger = logging.getLogger(__name__)

# Anonymous visitors act as the seeded guest-demo account ("1-Click Guest Demo"),
# never as "whoever signed up first": that would expose a real user's pantry and
# let anyone mint a Telegram link token for a real account.
DEMO_USERNAME = "ChefDemo"


def _guest_user():
    return User.objects.filter(username=DEMO_USERNAME).first()


from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from GetFood.throttles import scoped, _throttle_class
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .ai_service import (
    DEFAULT_AI_PROVIDER,
    ask_recipe_chat,
    generate_recipe_detail_meta,
    generate_recipe_suggestions,
    generate_recipe_suggestions_meta,
    normalize_language,
    scan_fridge_image,
    stream_recipe_generation,
)
from .models import (
    AISuggestionCache,
    Ingredient,
    Recipe,
    ShoppingListItem,
    TelegramAccountLink,
    UserPantry,
)
from .serializers import (
    IngredientSerializer,
    RecipeSerializer,
    UserPantrySerializer,
    UserSerializer,
)
from . import ai_cache
from .tasks import generate_ai_suggestions_task


# ==========================================
# REST Framework Model ViewSets
# ==========================================

class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all().order_by("name")
    serializer_class = IngredientSerializer
    throttle_classes = [_throttle_class("catalog")]


class RecipeViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Recipe.objects.all().order_by("name")
    serializer_class = RecipeSerializer
    throttle_classes = [_throttle_class("catalog")]


class UserPantryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = UserPantry.objects.all()
    serializer_class = UserPantrySerializer
    throttle_classes = [_throttle_class("catalog")]


@api_view(["GET"])
@permission_classes([AllowAny])
def api_stats(request):
    """Public platform counters for the landing page (Redis-cached for 60s)."""
    from django.core.cache import cache

    data = None
    try:
        data = cache.get("platform_stats")
    except Exception as e:
        # Cache backend unavailable (e.g. bare-metal run with Docker REDIS_URL):
        # degrade to computing live counters instead of failing the request.
        logger.warning("Stats cache read failure: %s", e)

    if data is None:
        data = {
            "total_recipes": Recipe.objects.count(),
            "total_ingredients": Ingredient.objects.count(),
            "total_users": User.objects.filter(is_active=True).count(),
        }
        try:
            cache.set("platform_stats", data, 60)
        except Exception as e:
            logger.warning("Stats cache write failure: %s", e)
    return Response(data)


@api_view(["GET"])
@permission_classes([AllowAny])
def api_health(request):
    """Liveness/readiness probe used by Docker healthchecks and load balancers."""
    checks = {"database": "down", "cache": "down", "broker": "skipped"}
    try:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        logger.warning("Health check DB failure: %s", e)

    try:
        from django.core.cache import cache

        cache.set("whattocook_health", "1", 10)
        if cache.get("whattocook_health") == "1":
            checks["cache"] = "ok"
        else:
            checks["cache"] = "degraded"
            logger.warning("Health check cache roundtrip returned unexpected value.")
    except Exception as e:
        # Redis/cache is optional at runtime (Celery has fallbacks); stay healthy without it.
        checks["cache"] = "degraded"
        logger.warning("Health check cache failure: %s", e)

    if getattr(settings, "HEALTH_CHECK_BROKER", False):
        try:
            from WhatToCook.celery import app as celery_app

            with celery_app.connection_for_read() as conn:
                conn.ensure_connection(max_retries=1, timeout=2)
            checks["broker"] = "ok"
        except Exception as e:
            # Queue outage degrades async fallbacks only; keep the pod serving.
            checks["broker"] = "degraded"
            logger.warning("Health check broker failure: %s", e)

    healthy = checks["database"] == "ok"
    payload = {"status": "ok" if healthy else "error", "checks": checks}
    return Response(payload, status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE)


# ==========================================
# Authentication REST APIs
# ==========================================

@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("auth")
def api_auth_login(request):
    """Log in user via JSON credentials."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response(
            {"error": "Please provide both username and password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=username, password=password)
    if user is not None:
        login(request, user)
        pantry, _ = UserPantry.objects.get_or_create(user=user)
        return Response({
            "message": "Login successful",
            "user": UserSerializer(user).data,
            "pantry": UserPantrySerializer(pantry).data,
        })
    return Response(
        {"error": "Invalid username or password."},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("signup")
def api_auth_signup(request):
    """Register a new user and initialize their pantry."""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")
    email = request.data.get("email", "").strip()

    if not username or not password:
        return Response(
            {"error": "Username and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return Response(
            {"error": f"Username '{username}' is already taken."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(username=username, password=password, email=email)
    pantry = UserPantry.objects.create(user=user)
    login(request, user)

    return Response({
        "message": "Account created successfully",
        "user": UserSerializer(user).data,
        "pantry": UserPantrySerializer(pantry).data,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@scoped("auth")
def api_auth_logout(request):
    """Log out current session."""
    logout(request)
    return Response({"message": "Logged out successfully"})


@api_view(["GET"])
@permission_classes([AllowAny])
def api_auth_me(request):
    """Get current user authentication info & pantry overview."""
    if request.user.is_authenticated:
        pantry, _ = UserPantry.objects.get_or_create(user=request.user)
        return Response({
            "authenticated": True,
            "user": UserSerializer(request.user).data,
            "pantry": UserPantrySerializer(pantry).data,
        })
    return Response({
        "authenticated": False,
        "user": None,
        "pantry": None,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("demo")
def api_auth_demo(request):
    """1-Click Guest Demo Login with pre-stocked kitchen pantry."""
    demo_user, created = User.objects.get_or_create(
        username=DEMO_USERNAME,
        defaults={"email": "chef@whattocook.local"}
    )
    if created:
        demo_user.set_password("demopassword123")
        demo_user.save()

    pantry, _ = UserPantry.objects.get_or_create(user=demo_user)

    # Stock pantry with standard ingredients if empty
    if pantry.ingredients.count() == 0:
        default_names = ["Eggs", "Flour", "Milk", "Butter", "Cheese", "Chicken Breast", "Tomato", "Garlic", "Onion", "Rice", "Salt", "Olive Oil"]
        for name in default_names:
            ing = Ingredient.objects.filter(name__iexact=name).first()
            if ing:
                pantry.ingredients.add(ing)

    login(request, demo_user)
    return Response({
        "message": "Logged in as ChefDemo",
        "user": UserSerializer(demo_user).data,
        "pantry": UserPantrySerializer(pantry).data,
    })


# ==========================================
# User Pantry REST APIs
# ==========================================

@api_view(["GET"])
@scoped("pantry")
def api_pantry_get(request):
    """Get current user pantry ingredients."""
    if not request.user.is_authenticated:
        # Fallback to first pantry or empty
        pantry = UserPantry.objects.filter(user__username=DEMO_USERNAME).first()
        if pantry:
            return Response(UserPantrySerializer(pantry).data)
        return Response({"ingredients": [], "total_ingredients": 0})

    pantry, _ = UserPantry.objects.get_or_create(user=request.user)
    return Response(UserPantrySerializer(pantry).data)


@api_view(["POST"])
@scoped("pantry")
def api_pantry_add(request):
    """Add ingredient(s) to the authenticated user's pantry."""
    user = request.user if request.user.is_authenticated else _guest_user()
    if not user:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    pantry, _ = UserPantry.objects.get_or_create(user=user)

    ingredient_id = request.data.get("ingredient_id")
    ingredient_name = request.data.get("name")
    ingredient_ids = request.data.get("ingredient_ids", [])

    added = []
    if ingredient_id:
        try:
            ing = Ingredient.objects.get(id=ingredient_id)
            pantry.ingredients.add(ing)
            added.append(ing.name)
        except Ingredient.DoesNotExist:
            return Response({"error": "Ingredient not found."}, status=404)

    elif ingredient_name:
        ing, _ = Ingredient.objects.get_or_create(name=ingredient_name.strip())
        pantry.ingredients.add(ing)
        added.append(ing.name)

    elif ingredient_ids:
        for i_id in ingredient_ids:
            try:
                ing = Ingredient.objects.get(id=i_id)
                pantry.ingredients.add(ing)
                added.append(ing.name)
            except Ingredient.DoesNotExist:
                continue

    return Response({
        "message": f"Added: {', '.join(added)}",
        "pantry": UserPantrySerializer(pantry).data,
    })


@api_view(["POST"])
@scoped("pantry")
def api_pantry_remove(request):
    """Remove ingredient from user's pantry."""
    user = request.user if request.user.is_authenticated else _guest_user()
    if not user:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    pantry, _ = UserPantry.objects.get_or_create(user=user)
    ingredient_id = request.data.get("ingredient_id")

    if not ingredient_id:
        return Response({"error": "ingredient_id is required."}, status=400)

    try:
        ing = Ingredient.objects.get(id=ingredient_id)
        pantry.ingredients.remove(ing)
        return Response({
            "message": f"Removed {ing.name}",
            "pantry": UserPantrySerializer(pantry).data,
        })
    except Ingredient.DoesNotExist:
        return Response({"error": "Ingredient not found."}, status=404)


@api_view(["POST"])
@scoped("pantry")
def api_pantry_clear(request):
    """Clear all ingredients in user's pantry."""
    user = request.user if request.user.is_authenticated else _guest_user()
    if not user:
        return Response({"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST)

    pantry, _ = UserPantry.objects.get_or_create(user=user)
    pantry.ingredients.clear()
    return Response({
        "message": "Pantry cleared",
        "pantry": UserPantrySerializer(pantry).data,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("scan", "scan_day")
def api_pantry_scan_image(request):
    """
    Multimodal Vision Fridge & Pantry Scanner.
    Accepts an uploaded image file or base64 data, uses Gemini Vision AI to detect
    all visible food ingredients, and optionally auto-adds them to the user's pantry.
    """
    image_file = request.FILES.get("image")
    image_base64 = request.data.get("image_base64")
    auto_add = request.data.get("auto_add", False)
    provider = request.data.get("provider", DEFAULT_AI_PROVIDER)
    language = request.data.get("language")

    if not image_file and not image_base64:
        return Response(
            {"error": "Please provide an image file ('image') or base64 data ('image_base64')."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --- Upload hardening: reject non-images, oversized payloads ---------
    MAX_SCAN_BYTES = int(os.environ.get("SCAN_MAX_BYTES", str(8 * 1024 * 1024)))
    mime_type = "image/jpeg"
    image_bytes = None

    if image_file:
        if image_file.size > MAX_SCAN_BYTES:
            return Response(
                {"error": "Image too large (max 8 MB). Please upload a smaller photo."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        raw = image_file.read()
        content_type = (image_file.content_type or "").lower()
        if content_type and not content_type.startswith("image/"):
            return Response(
                {"error": "Unsupported file type. Upload a JPEG, PNG or WebP image."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(raw) < 32:  # empty / truncated uploads
            return Response(
                {"error": "The uploaded file appears to be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        image_bytes = raw
        mime_type = content_type or "image/jpeg"
    elif image_base64:
        if len(image_base64) > MAX_SCAN_BYTES * 2:
            return Response(
                {"error": "Image too large (max 8 MB). Please upload a smaller photo."},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        import base64
        if "," in image_base64:
            header, encoded = image_base64.split(",", 1)
            if "png" in header:
                mime_type = "image/png"
            elif "webp" in header:
                mime_type = "image/webp"
            image_bytes = base64.b64decode(encoded)
        else:
            image_bytes = base64.b64decode(image_base64)

    detected_items = scan_fridge_image(image_bytes, mime_type=mime_type, provider=provider, language=language)

    added_names = []
    pantry_data = None

    # Handle auto-add or user-requested immediate save
    user = request.user if request.user.is_authenticated else _guest_user()
    if auto_add and user:
        pantry, _ = UserPantry.objects.get_or_create(user=user)
        for item in detected_items:
            name = item.get("name")
            if name:
                ing, _ = Ingredient.objects.get_or_create(
                    name=name,
                    defaults={"category": item.get("category", "Produce")}
                )
                pantry.ingredients.add(ing)
                added_names.append(ing.name)
        pantry_data = UserPantrySerializer(pantry).data

    return Response({
        "status": "success",
        "detected_count": len(detected_items),
        "detected_ingredients": detected_items,
        "auto_added": auto_add,
        "added_ingredients": added_names,
        "pantry": pantry_data,
    })


# ==========================================
# Smart Recipe Matching ("Can Cook") API
# ==========================================

@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("can_cook")
def api_can_cook(request):
    """
    Calculate recipes match against user pantry ingredients.
    Returns:
    - 100% matched recipes (can fully cook)
    - partial matches (missing 1 or 2 ingredients) with match percentages
    """
    user = request.user if request.user.is_authenticated else _guest_user()
    pantry_ingredients = set()
    if user:
        pantry = UserPantry.objects.filter(user=user).first()
        if pantry:
            pantry_ingredients = set(pantry.ingredients.values_list("id", flat=True))

    all_recipes = Recipe.objects.prefetch_related("recipeingredient_set__ingredient").all()

    full_matches = []
    partial_matches = []

    for recipe in all_recipes:
        recipe_ing_ids = set(recipe.recipeingredient_set.values_list("ingredient_id", flat=True))
        total_required = len(recipe_ing_ids)
        if total_required == 0:
            continue

        matched_ids = recipe_ing_ids.intersection(pantry_ingredients)
        missing_ids = recipe_ing_ids.difference(pantry_ingredients)
        match_count = len(matched_ids)
        missing_count = len(missing_ids)

        match_pct = round((match_count / total_required) * 100)

        missing_names = list(
            Ingredient.objects.filter(id__in=missing_ids).values_list("name", flat=True)
        )
        matched_names = list(
            Ingredient.objects.filter(id__in=matched_ids).values_list("name", flat=True)
        )

        recipe_data = RecipeSerializer(recipe, context={"request": request}).data
        recipe_data["match_percentage"] = match_pct
        recipe_data["missing_count"] = missing_count
        recipe_data["missing_ingredients"] = missing_names
        recipe_data["matched_ingredients"] = matched_names

        if missing_count == 0:
            full_matches.append(recipe_data)
        elif missing_count <= 2 or match_pct >= 50:
            partial_matches.append(recipe_data)

    # Sort partial matches by match percentage descending
    partial_matches.sort(key=lambda x: x["match_percentage"], reverse=True)

    return Response({
        "full_matches": full_matches,
        "partial_matches": partial_matches,
        "pantry_ingredient_count": len(pantry_ingredients),
        "total_full_matches": len(full_matches),
        "total_partial_matches": len(partial_matches),
    })


# ==========================================
# AI Chef Suggestion & Recipe Detail APIs
# ==========================================
# AI Provider Health, Dynamic Models & Telegram APIs
# ==========================================

def _check_lmstudio_health():
    """Verify if LM Studio is actively running and serving models on port 1234."""
    urls_to_try = [
        "http://127.0.0.1:1234/v1/models",
        "http://localhost:1234/v1/models",
    ]
    if getattr(settings, "LMSTUDIO_URL", ""):
        base = settings.LMSTUDIO_URL.replace("/chat/completions", "/models")
        if base not in urls_to_try:
            urls_to_try.append(base)

    for url in urls_to_try:
        try:
            resp = requests.get(url, timeout=0.6)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if m.get("id")]
                return {
                    "online": True,
                    "model": models[0] if models else settings.MODEL_NAME,
                    "available_models": models,
                    "url": url,
                }
        except Exception:
            continue

    return {
        "online": False,
        "model": settings.MODEL_NAME,
        "available_models": [],
        "error": "LM Studio is offline. Start LM Studio on port 1234 to enable Local AI.",
    }


@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("ai_meta")
def api_ai_providers(request):
    """Return live available AI configurations with real-time health verification."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    has_gemini = bool(api_key)
    current_gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash") or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    lm_health = _check_lmstudio_health()

    return Response({
        "default_provider": DEFAULT_AI_PROVIDER,
        "has_gemini": has_gemini,
        "gemini_model": current_gemini_model,
        "has_lmstudio": lm_health["online"],
        "lmstudio_online": lm_health["online"],
        "lmstudio_model": lm_health["model"],
        "lmstudio_error": lm_health.get("error"),
        "providers": [
            {
                "id": "gemini",
                "name": f"Cloud AI ({current_gemini_model})",
                "active": has_gemini,
                "online": has_gemini,
                "badge": "Ultra-Fast & Smart",
            },
            {
                "id": "lmstudio",
                "name": f"Local AI ({lm_health['model']})",
                "active": lm_health["online"],
                "online": lm_health["online"],
                "badge": "Offline Ready" if lm_health["online"] else "Offline (Not Running)",
            }
        ]
    })


@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("ai_meta")
def api_ai_models(request):
    """List available Google Gemini models dynamically from the Google AI Studio endpoint."""
    api_key = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
    default_model = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    curated_fallback_models = [
        {"id": "gemini-3.5-flash-lite", "displayName": "Gemini 3.5 Flash Lite (Max Free Quota - Default)"},
        {"id": "gemini-3.6-flash", "displayName": "Gemini 3.6 Flash (High Performance & Fast)"},
        {"id": "gemini-3.5-flash", "displayName": "Gemini 3.5 Flash"},
        {"id": "gemini-2.5-flash-lite", "displayName": "Gemini 2.5 Flash Lite"},
        {"id": "gemini-2.5-flash", "displayName": "Gemini 2.5 Flash"},
        {"id": "gemini-2.0-flash", "displayName": "Gemini 2.0 Flash"},
    ]

    if not api_key:
        return Response({
            "models": curated_fallback_models,
            "current_model": default_model,
            "is_live": False,
        })

    try:
        resp = requests.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
            timeout=5.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            raw_models = data.get("models", [])
            models = []
            seen_ids = set()

            # Free-tier Flash models prioritized; Pro models are excluded because they require paid tiers
            priority_names = [
                "gemini-3.5-flash-lite",
                "gemini-3.6-flash",
                "gemini-3.5-flash",
                "gemini-3.1-flash-lite",
                "gemini-2.5-flash-lite",
                "gemini-2.5-flash",
                "gemini-2.0-flash-lite",
                "gemini-2.0-flash",
                "gemini-flash-latest",
            ]

            raw_dict = {m.get("name", "").replace("models/", ""): m for m in raw_models}

            for p in priority_names:
                if p in raw_dict and p not in seen_ids:
                    m = raw_dict[p]
                    models.append({
                        "id": p,
                        "displayName": m.get("displayName", p),
                        "description": m.get("description", ""),
                    })
                    seen_ids.add(p)
                elif p not in seen_ids:
                    # Also include our curated free flash models even if not explicitly in Google's dynamic list
                    fallback_match = next((item for item in curated_fallback_models if item["id"] == p), None)
                    if fallback_match:
                        models.append(fallback_match)
                        seen_ids.add(p)

            for m in raw_models:
                name = m.get("name", "").replace("models/", "")
                # Exclude 'pro' models, non-gemini, and special-purpose models
                if (
                    name not in seen_ids
                    and "gemini" in name
                    and "pro" not in name.lower()
                    and not name.endswith("-tts")
                    and "embedding" not in name
                    and "image" not in name
                    and "robotics" not in name
                    and "computer-use" not in name
                ):
                    models.append({
                        "id": name,
                        "displayName": m.get("displayName", name),
                        "description": m.get("description", ""),
                    })
                    seen_ids.add(name)

            return Response({
                "models": models if models else curated_fallback_models,
                "current_model": default_model,
                "is_live": True,
            })
    except Exception as e:
        logger.warning("Failed to query Gemini models API: %s", e)

    return Response({
        "models": curated_fallback_models,
        "current_model": default_model,
        "is_live": False,
    })


@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("telegram_link")
def api_telegram_link(request):
    """Generate instant Telegram Bot connection handshake link."""
    user = request.user if request.user.is_authenticated else _guest_user()
    auth_token = f"auth_{user.id if user else 1}_{os.urandom(4).hex()}"
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "WhatToCook_AIBot")

    connect_url = f"https://t.me/{bot_username}?start={auth_token}"
    direct_tg_url = f"tg://resolve?domain={bot_username}&start={auth_token}"
    web_tg_url = f"https://web.telegram.org/k/#?tgaddr=resolve?domain={bot_username}&start={auth_token}"

    return Response({
        "auth_token": auth_token,
        "is_connected": False,
        "bot_username": bot_username,
        "connect_url": connect_url,
        "direct_tg_url": direct_tg_url,
        "web_tg_url": web_tg_url,
    })


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
@scoped("ai", "ai_day")
def ai_suggestions_api(request):
    """
    Generate AI recipe ideas from pantry ingredients or custom ingredient list.
    Supports provider selection: 'gemini' | 'lmstudio' and specific model selection.
    """
    provider = request.data.get("provider") if request.method == "POST" else request.GET.get("provider")
    model = request.data.get("model") if request.method == "POST" else request.GET.get("model")
    custom_ingredients = request.data.get("ingredients") if request.method == "POST" else None
    force_refresh = request.data.get("force_refresh", False) if request.method == "POST" else request.GET.get("force_refresh", False)
    language = request.data.get("language") if request.method == "POST" else request.GET.get("language")

    if custom_ingredients and isinstance(custom_ingredients, list) and len(custom_ingredients) > 0:
        ingredients = [str(i).strip() for i in custom_ingredients if str(i).strip()]
    else:
        user = request.user if request.user.is_authenticated else _guest_user()
        try:
            pantry = UserPantry.objects.get(user=user)
            ingredients = [i.name for i in pantry.ingredients.all()]
        except (UserPantry.DoesNotExist, AttributeError):
            ingredients = ["Eggs", "Flour", "Tomato", "Cheese", "Garlic"]

    if not ingredients:
        ingredients = ["Tomato", "Garlic", "Eggs", "Cheese", "Pasta"]

    ingredients_str = ", ".join(sorted([i.lower() for i in ingredients]))
    lang_code = normalize_language(language) or ""
    ingredients_hash = hashlib.sha256(
        f"{ingredients_str}:{provider or 'default'}:{model or 'default'}:{lang_code}".encode()
    ).hexdigest()

    def _cached_response(recipes):
        return Response({
            "status": "done",
            "recipes": recipes,
            "cached": True,
            "provider": provider or DEFAULT_AI_PROVIDER,
            "model": model,
            "model_used": model or getattr(settings, "GEMINI_MODEL", "gemini-3.6-flash"),
            "rate_limited_models": [],
        })

    # Check 24h cache unless force_refresh requested:
    # Redis hot layer first, then the durable DB table (re-warming Redis).
    if not force_refresh:
        hot = ai_cache.get_suggestions(ingredients_hash)
        if hot:
            return _cached_response(hot)

        cache_entry = AISuggestionCache.objects.filter(
            ingredients_hash=ingredients_hash,
            created_at__gte=timezone.now() - timedelta(days=1)
        ).first()

        if cache_entry and isinstance(cache_entry.ai_response, list) and len(cache_entry.ai_response) > 0:
            ai_cache.set_suggestions(ingredients_hash, cache_entry.ai_response)
            return _cached_response(cache_entry.ai_response)

    # Generate suggestions directly with metadata
    try:
        recipes, model_used, rate_limited_models = generate_recipe_suggestions_meta(ingredients, provider=provider, model=model, language=language)
        # Store in cache
        if not ai_cache.is_degraded(recipes):  # never cache the AI-offline fallback
            AISuggestionCache.objects.update_or_create(
                ingredients_hash=ingredients_hash,
                defaults={"ai_response": recipes, "created_at": timezone.now()}
            )
            ai_cache.set_suggestions(ingredients_hash, recipes)
        return Response({
            "status": "done",
            "recipes": recipes,
            "cached": False,
            "provider": provider or DEFAULT_AI_PROVIDER,
            "model": model,
            "model_used": model_used,
            "rate_limited_models": rate_limited_models,
        })
    except Exception:
        # Fallback to Celery background task if direct call is slow or fails
        try:
            task = generate_ai_suggestions_task.delay(ingredients, ingredients_hash, provider, language)
            ai_cache.remember_task(task.id, ingredients_hash)
            return Response({"status": "processing", "task_id": task.id})
        except Exception:
            # Return safe fallback recipes
            fallback = generate_recipe_suggestions(ingredients, provider="fallback")
            return Response({
                "status": "done",
                "recipes": fallback,
                "cached": False,
                "model_used": "fallback",
                "rate_limited_models": [],
            })


@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("ai", "ai_day")
def ai_recipe_detail_api(request, recipe_name):
    """Get full master chef recipe breakdown for an AI suggested dish."""
    provider = request.GET.get("provider")
    model = request.GET.get("model")
    language = request.GET.get("language")
    try:
        recipe_data, model_used, rate_limited_models = generate_recipe_detail_meta(recipe_name, provider=provider, model=model, language=language)
        return Response(recipe_data)
    except Exception as e:
        return Response({"error": f"Error generating recipe details: {e}"}, status=500)


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("ai", "ai_day")
def api_recipe_chat(request):
    """
    AI Sous-Chef interactive conversation about a specific recipe.
    Accepts: { recipe_name, ingredients, instructions, message, history, provider, model }
    Returns: { reply, model_used, rate_limited_models, recipe_name }
    """
    recipe_name = request.data.get("recipe_name", "Dish")
    ingredients = request.data.get("ingredients")
    instructions = request.data.get("instructions")
    user_question = request.data.get("message", "").strip()
    history = request.data.get("history", [])
    provider = request.data.get("provider")
    model = request.data.get("model")
    language = request.data.get("language")

    if not user_question:
        return Response({"error": "Message is required."}, status=400)

    try:
        result = ask_recipe_chat(
            recipe_name=recipe_name,
            ingredients=ingredients,
            instructions=instructions,
            user_question=user_question,
            history=history,
            provider=provider,
            model=model,
            language=language,
        )
        return Response(result)
    except Exception as e:
        logger.warning(f"Error in api_recipe_chat: {e}")
        return Response({
            "reply": f"As your sous-chef for {recipe_name}, let me help! For best results, adjust seasonings to taste and let cooked items rest for 2-3 minutes before serving.",
            "model_used": "fallback",
            "rate_limited_models": [],
            "recipe_name": recipe_name,
        })



# ==========================================
# Shopping List REST APIs (Multi-Tier Persistence)
# ==========================================

@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_get(request):
    """Retrieve all shopping list items from the database."""
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or "guest_default"

    if user:
        items = ShoppingListItem.objects.filter(user=user)
    else:
        items = ShoppingListItem.objects.filter(session_key=session_key)

    data = [
        {
            "id": str(item.id),
            "name": item.name,
            "category": item.category,
            "quantity": item.quantity,
            "checked": item.checked,
            "added_from": item.added_from,
            "created_at": item.created_at.isoformat(),
        }
        for item in items
    ]
    return Response({"items": data, "count": len(data)})


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_add(request):
    """Add a single item or multiple items to the shopping list."""
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or "guest_default"

    items_data = request.data.get("items")
    single_name = request.data.get("name")

    created_items = []
    if items_data and isinstance(items_data, list):
        for entry in items_data:
            name = entry.get("name", "").strip()
            if name:
                item = ShoppingListItem.objects.create(
                    user=user,
                    session_key=session_key if not user else "",
                    name=name,
                    category=entry.get("category", "General"),
                    quantity=entry.get("quantity", "1 item"),
                    checked=entry.get("checked", False),
                    added_from=entry.get("added_from"),
                )
                created_items.append(item)
    elif single_name:
        item = ShoppingListItem.objects.create(
            user=user,
            session_key=session_key if not user else "",
            name=single_name.strip(),
            category=request.data.get("category", "General"),
            quantity=request.data.get("quantity", "1 item"),
            checked=request.data.get("checked", False),
            added_from=request.data.get("added_from"),
        )
        created_items.append(item)

    return Response({
        "status": "success",
        "added_count": len(created_items),
        "items": [
            {
                "id": str(item.id),
                "name": item.name,
                "category": item.category,
                "quantity": item.quantity,
                "checked": item.checked,
                "added_from": item.added_from,
            }
            for item in created_items
        ]
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_sync(request):
    """Bulk sync entire local shopping list into the database."""
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or "guest_default"

    incoming_items = request.data.get("items", [])
    if not isinstance(incoming_items, list):
        return Response({"error": "Invalid items format"}, status=400)

    # Clear existing session/user list and replace with full sync
    if user:
        ShoppingListItem.objects.filter(user=user).delete()
    else:
        ShoppingListItem.objects.filter(session_key=session_key).delete()

    created_items = []
    for entry in incoming_items:
        name = entry.get("name", "").strip()
        if name:
            item = ShoppingListItem.objects.create(
                user=user,
                session_key=session_key if not user else "",
                name=name,
                category=entry.get("category", "General"),
                quantity=entry.get("quantity", "1 item"),
                checked=entry.get("checked", False),
                added_from=entry.get("added_from"),
            )
            created_items.append(item)

    return Response({
        "status": "synced",
        "count": len(created_items),
    })


@api_view(["PATCH", "PUT"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_toggle(request, item_id):
    """Toggle or update an existing shopping list item."""
    try:
        item = ShoppingListItem.objects.get(id=item_id)
        if "checked" in request.data:
            item.checked = bool(request.data["checked"])
        if "name" in request.data:
            item.name = request.data["name"].strip()
        if "quantity" in request.data:
            item.quantity = request.data["quantity"].strip()
        if "category" in request.data:
            item.category = request.data["category"].strip()
        item.save()
        return Response({"status": "updated", "id": item.id, "checked": item.checked})
    except ShoppingListItem.DoesNotExist:
        return Response({"error": "Item not found"}, status=404)


@api_view(["DELETE"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_remove(request, item_id):
    """Remove a single item from the shopping list."""
    ShoppingListItem.objects.filter(id=item_id).delete()
    return Response({"status": "deleted", "id": item_id})


@api_view(["POST", "DELETE"])
@permission_classes([AllowAny])
@scoped("shopping")
def api_shopping_list_clear(request):
    """Clear completed items or all items from the shopping list."""
    user = request.user if request.user.is_authenticated else None
    session_key = request.session.session_key or "guest_default"
    only_completed = request.data.get("only_completed", False) if request.method == "POST" else request.GET.get("only_completed", False)

    qs = ShoppingListItem.objects.filter(user=user) if user else ShoppingListItem.objects.filter(session_key=session_key)
    if only_completed:
        qs = qs.filter(checked=True)
    
    deleted_count, _ = qs.delete()
    return Response({"status": "cleared", "deleted_count": deleted_count})



@api_view(["GET"])
@permission_classes([AllowAny])
def ai_task_status(request, task_id):
    """Poll Celery task status."""
    from celery.result import AsyncResult

    res = AsyncResult(task_id)
    if not res.ready():
        return Response({"status": "pending"})
    if res.failed():
        # Retries exhausted. Don't leak the exception text to anonymous pollers.
        logger.warning("AI task %s failed: %s", task_id, res.result)
        return Response({"status": "error", "error": "AI generation failed. Please try again."})

    # Resolve *this* task's result: task id -> ingredient hash -> Redis/DB.
    ingredients_hash = ai_cache.task_hash(task_id)
    if ingredients_hash:
        hot = ai_cache.get_suggestions(ingredients_hash)
        if hot:
            return Response({"status": "done", "recipes": hot})

    # Fallback (task id unknown to Redis, e.g. after a flush): newest recent
    # entry, narrowed to this task's hash when we know it.
    qs = AISuggestionCache.objects.filter(
        created_at__gte=timezone.now() - timedelta(minutes=15)
    )
    if ingredients_hash:
        qs = qs.filter(ingredients_hash=ingredients_hash)
    cache_entry = qs.order_by("-created_at").first()

    if cache_entry and isinstance(cache_entry.ai_response, list):
        return Response({"status": "done", "recipes": cache_entry.ai_response})
    return Response({"status": "done", "recipes": []})


# ==========================================
# Legacy Template Views (Backwards Compatibility)
# ==========================================

def index(request):
    recipes = Recipe.objects.all()
    ingredients = Ingredient.objects.all()
    user_pantry = UserPantry.objects.filter(user__username=DEMO_USERNAME).first()

    page = request.GET.get("page", 1)
    paginator = Paginator(recipes, 6)
    try:
        paginated_recipes = paginator.page(page)
    except PageNotAnInteger:
        paginated_recipes = paginator.page(1)
    except EmptyPage:
        paginated_recipes = paginator.page(paginator.num_pages)

    context = {
        "recipes": paginated_recipes,
        "ingredients": ingredients,
        "user_pantry": user_pantry,
        "num_pages": paginator.num_pages,
        "current_page": paginated_recipes.number,
    }
    return render(request, "GetFood/index.html", context)


@login_required
def pantry(request):
    user_pantry, _ = UserPantry.objects.get_or_create(user=request.user)
    ingredients = user_pantry.ingredients.all()
    available_ingredients = Ingredient.objects.exclude(id__in=ingredients)

    if request.method == "POST":
        if "ingredient_id" in request.POST:
            ingredient_id = request.POST.get("ingredient_id")
            if ingredient_id:
                ingredient = Ingredient.objects.get(id=ingredient_id)
                user_pantry.ingredients.add(ingredient)
                return redirect("pantry")
        elif "remove_id" in request.POST:
            remove_id = request.POST.get("remove_id")
            if remove_id:
                ingredient = Ingredient.objects.get(id=remove_id)
                user_pantry.ingredients.remove(ingredient)
                return redirect("pantry")

    return render(request, "GetFood/pantry.html", {
        "ingredients": ingredients,
        "available_ingredients": available_ingredients,
    })


def recipe_detail(request, recipe_id):
    recipe = get_object_or_404(Recipe, id=recipe_id)
    instructions_list = recipe.instructions.split("\n") if recipe.instructions else []
    return render(request, "GetFood/recipe_detail.html", {
        "recipe": recipe,
        "instructions_list": instructions_list,
    })


def can_cook(request):
    user = request.user
    pantry_ingredients = []
    if user.is_authenticated:
        try:
            pantry = UserPantry.objects.get(user=user)
            pantry_ingredients = pantry.ingredients.all()
        except UserPantry.DoesNotExist:
            pantry_ingredients = []

    possible_recipes = []
    for recipe in Recipe.objects.all():
        recipe_ingredients = [ri.ingredient for ri in recipe.recipeingredient_set.all()]
        if all(ingredient in pantry_ingredients for ingredient in recipe_ingredients):
            possible_recipes.append(recipe)

    paginator = Paginator(possible_recipes, 6)
    page = request.GET.get("page", 1)
    try:
        paginated_recipes = paginator.page(page)
    except PageNotAnInteger:
        paginated_recipes = paginator.page(1)
    except EmptyPage:
        paginated_recipes = paginator.page(paginator.num_pages)

    return render(request, "GetFood/can_cook.html", {
        "possible_recipes": paginated_recipes,
        "pantry_ingredients": pantry_ingredients,
        "num_pages": paginator.num_pages,
        "current_page": paginated_recipes.number,
    })


def signup_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserPantry.objects.create(user=user)
            login(request, user)
            return redirect("index")
    else:
        form = UserCreationForm()
    return render(request, "GetFood/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("index")
    else:
        form = AuthenticationForm()
    return render(request, "GetFood/login.html", {"form": form})


@login_required
def ai_suggestions(request):
    return render(request, "GetFood/ai_suggestions.html")


@login_required
def ai_recipe_detail(request, name):
    return render(request, "GetFood/ai_recipe_detail.html", {"recipe_name": name})


# ==========================================
# Real-Time Streaming AI Recipe API (SSE)
# ==========================================

@api_view(["GET"])
@permission_classes([AllowAny])
@scoped("ai", "ai_hour")
def api_ai_stream_recipe(request):
    """
    Stream live gourmet recipe token-by-token using Server-Sent Events (SSE).
    Params: ?recipe=Gourmet%20Dish&provider=gemini
    """
    recipe_name = request.GET.get("recipe", "Chef's Special Creation")
    provider = request.GET.get("provider", DEFAULT_AI_PROVIDER)
    language = request.GET.get("language")

    response = StreamingHttpResponse(
        stream_recipe_generation(recipe_name, provider=provider, language=language),
        content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


# ==========================================
# Telegram Bot Integration APIs
# ==========================================

@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def api_telegram_get_link(request):
    """Generate or retrieve a Telegram connection token for the logged-in user."""
    user = request.user if request.user.is_authenticated else _guest_user()
    if not user:
        user, _ = User.objects.get_or_create(username="chef_demo")

    link = TelegramAccountLink.generate_token_for_user(user)
    bot_username = getattr(settings, "TELEGRAM_BOT_USERNAME", "WhatToCookChefBot") or os.getenv("TELEGRAM_BOT_USERNAME", "WhatToCookChefBot")

    connect_url = f"https://t.me/{bot_username}?start={link.auth_token}"
    direct_tg_url = f"tg://resolve?domain={bot_username}&start={link.auth_token}"
    web_tg_url = f"https://web.telegram.org/a/#?tgaddr=resolve?domain={bot_username}&start={link.auth_token}"

    return Response({
        "auth_token": link.auth_token,
        "is_connected": bool(link.telegram_chat_id),
        "telegram_username": link.telegram_username,
        "bot_username": bot_username,
        "connect_url": connect_url,
        "direct_tg_url": direct_tg_url,
        "web_tg_url": web_tg_url,
    })


@csrf_exempt
@api_view(["POST"])
@permission_classes([AllowAny])
@scoped("telegram_webhook")
def api_telegram_webhook(request):
    """
    Telegram Bot Webhook endpoint.
    Handles bot commands: /start <token>, /pantry, /add <item>, /remove <item>, /cook, /shoppinglist
    """
    # Optional shared-secret verification (Telegram sends the header you
    # configured via setWebhook secret_token). Enables a public webhook URL.
    expected_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "") or getattr(
        settings, "TELEGRAM_WEBHOOK_SECRET", ""
    )
    if expected_secret:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != expected_secret:
            return Response(
                {"error": "Invalid webhook secret."},
                status=status.HTTP_403_FORBIDDEN,
            )

    update = request.data
    message = update.get("message") or update.get("channel_post")
    if not message:
        return Response({"status": "ignored"})

    chat_id = str(message.get("chat", {}).get("id", ""))
    username = message.get("from", {}).get("username", "")
    text = (message.get("text") or "").strip()

    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")

    def _send_tg_reply(reply_text: str):
        if not bot_token or not chat_id:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": reply_text, "parse_mode": "Markdown"},
                timeout=10,
            )
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")

    # Command: /start <token>
    if text.startswith("/start"):
        parts = text.split()
        if len(parts) > 1:
            token = parts[1].strip()
            link = TelegramAccountLink.objects.filter(auth_token=token).first()
            if link:
                link.telegram_chat_id = chat_id
                link.telegram_username = username
                link.save()
                _send_tg_reply(
                    f"🎉 *Account Connected!*\n\nWelcome Chef *{link.user.username}*!\n"
                    "You can now manage your WhatToCook kitchen directly on Telegram:\n\n"
                    "• `/pantry` - View your pantry ingredients\n"
                    "• `/add <ingredient>` - Add items (e.g. `/add Garlic`)\n"
                    "• `/remove <ingredient>` - Remove items\n"
                    "• `/cook` - Ask AI Chef what you can cook right now\n"
                    "• `/shoppinglist` - Get missing ingredients"
                )
                return Response({"status": "connected", "user": link.user.username})
            else:
                _send_tg_reply("❌ Invalid or expired connection token. Please generate a new link in your WhatToCook Web App.")
                return Response({"status": "invalid_token"})
        else:
            _send_tg_reply(
                "👋 Welcome to *WhatToCook AI Chef Bot*!\n\n"
                "To connect your account, click the 'Connect Telegram' button in your WhatToCook web app."
            )
            return Response({"status": "welcome"})

    # Find connected account
    link = TelegramAccountLink.objects.filter(telegram_chat_id=chat_id, is_active=True).first()
    if not link:
        _send_tg_reply("🔒 Please link your account first by starting with your authorization link from the WhatToCook web app.")
        return Response({"status": "unlinked"})

    user = link.user
    pantry, _ = UserPantry.objects.get_or_create(user=user)

    # Command: /pantry
    if text.startswith("/pantry"):
        items = list(pantry.ingredients.values_list("name", flat=True))
        if items:
            list_str = "\n".join([f"• {i.title()}" for i in items])
            _send_tg_reply(f"🛒 *Your Kitchen Pantry ({len(items)} items):*\n\n{list_str}")
        else:
            _send_tg_reply("🥫 Your pantry is currently empty! Use `/add <item>` to stock it up.")
        return Response({"status": "pantry_viewed"})

    # Command: /add <item>
    elif text.startswith("/add"):
        ing_name = text[4:].strip()
        if ing_name:
            ing, _ = Ingredient.objects.get_or_create(name=ing_name.title())
            pantry.ingredients.add(ing)
            _send_tg_reply(f"✅ Added *{ing.name}* to your pantry shelf!")
        else:
            _send_tg_reply("Please specify an ingredient name. Example: `/add Olive Oil`")
        return Response({"status": "ingredient_added"})

    # Command: /remove <item>
    elif text.startswith("/remove"):
        ing_name = text[7:].strip()
        if ing_name:
            ing = Ingredient.objects.filter(name__iexact=ing_name).first()
            if ing and ing in pantry.ingredients.all():
                pantry.ingredients.remove(ing)
                _send_tg_reply(f"🗑️ Removed *{ing.name}* from your pantry.")
            else:
                _send_tg_reply(f"Could not find *{ing_name}* in your active pantry.")
        else:
            _send_tg_reply("Please specify an ingredient name. Example: `/remove Tomato`")
        return Response({"status": "ingredient_removed"})

    # Command: /cook
    elif text.startswith("/cook"):
        items = list(pantry.ingredients.values_list("name", flat=True))
        if not items:
            _send_tg_reply("🥫 Your pantry is empty! Add ingredients first with `/add <item>`.")
            return Response({"status": "empty_pantry"})

        _send_tg_reply("👨‍🍳 *Chef is inspecting your ingredients & creating recipes...*")
        suggestions = generate_recipe_suggestions(items)
        reply = "🍽️ *Here is what you can cook:*\n\n"
        for s in suggestions[:4]:
            reply += f"✨ *{s.get('name')}* ({s.get('prep_time', '25 mins')})\n_{s.get('short_description')}_\n\n"
        _send_tg_reply(reply)
        return Response({"status": "recipes_suggested"})

    # Default help
    _send_tg_reply(
        "🍳 *WhatToCook Commands:*\n"
        "• `/pantry` - View stocked ingredients\n"
        "• `/add <ingredient>` - Stock an item\n"
        "• `/remove <ingredient>` - Delete an item\n"
        "• `/cook` - Get instant AI recipe ideas"
    )
    return Response({"status": "help_sent"})
