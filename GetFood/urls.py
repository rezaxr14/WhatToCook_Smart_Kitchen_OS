from django.contrib.auth import views as auth_views
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .views import (
    IngredientViewSet,
    RecipeViewSet,
    UserPantryViewSet,
    ai_recipe_detail_api,
    ai_suggestions_api,
    ai_task_status,
    api_ai_models,
    api_ai_providers,
    api_ai_stream_recipe,
    api_recipe_chat,
    api_auth_demo,
    api_auth_challenge,
    api_auth_login,
    api_auth_logout,
    api_auth_me,
    api_auth_signup,
    api_can_cook,
    api_health,
    api_pantry_add,
    api_pantry_clear,
    api_pantry_get,
    api_pantry_remove,
    api_pantry_scan_image,
    api_shopping_list_add,
    api_shopping_list_clear,
    api_shopping_list_get,
    api_shopping_list_remove,
    api_shopping_list_sync,
    api_shopping_list_toggle,
    api_stats,
    api_telegram_get_link,
    api_telegram_webhook,
)

router = DefaultRouter()
router.register("ingredients", IngredientViewSet)
router.register("recipes", RecipeViewSet)
router.register("pantries", UserPantryViewSet)

urlpatterns = [
    # DRF Model ViewSets
    path("api/", include(router.urls)),

    # Platform
    path("api/stats/", api_stats, name="api_stats"),
    path("api/health/", api_health, name="api_health"),

    # Auth REST APIs
    path("api/auth/login/", api_auth_login, name="api_auth_login"),
    path("api/auth/signup/", api_auth_signup, name="api_auth_signup"),
    path("api/auth/logout/", api_auth_logout, name="api_auth_logout"),
    path("api/auth/me/", api_auth_me, name="api_auth_me"),
    path("api/auth/demo/", api_auth_demo, name="api_auth_demo"),
    path("api/auth/challenge/", api_auth_challenge, name="api_auth_challenge"),

    # Pantry REST APIs
    path("api/pantry/", api_pantry_get, name="api_pantry_get"),
    path("api/pantry/add/", api_pantry_add, name="api_pantry_add"),
    path("api/pantry/remove/", api_pantry_remove, name="api_pantry_remove"),
    path("api/pantry/clear/", api_pantry_clear, name="api_pantry_clear"),
    path("api/pantry/scan-image/", api_pantry_scan_image, name="api_pantry_scan_image"),

    # Shopping List REST APIs (Local cache + DB saves)
    path("api/shopping-list/", api_shopping_list_get, name="api_shopping_list_get"),
    path("api/shopping-list/add/", api_shopping_list_add, name="api_shopping_list_add"),
    path("api/shopping-list/sync/", api_shopping_list_sync, name="api_shopping_list_sync"),
    path("api/shopping-list/<int:item_id>/", api_shopping_list_toggle, name="api_shopping_list_toggle"),
    path("api/shopping-list/<int:item_id>/delete/", api_shopping_list_remove, name="api_shopping_list_remove"),
    path("api/shopping-list/clear/", api_shopping_list_clear, name="api_shopping_list_clear"),

    # Smart Matching
    path("api/can-cook/", api_can_cook, name="api_can_cook"),

    # AI Chef Endpoints
    path("api/ai/providers/", api_ai_providers, name="api_ai_providers"),
    path("api/ai/models/", api_ai_models, name="api_ai_models"),
    path("api/ai/suggestions/", ai_suggestions_api, name="api_ai_suggestions"),
    path("api/ai/recipe/<str:recipe_name>/", ai_recipe_detail_api, name="api_ai_recipe_detail"),
    path("api/ai/recipe-chat/", api_recipe_chat, name="api_recipe_chat"),
    path("api/ai/task-status/<str:task_id>/", ai_task_status, name="api_ai_task_status"),
    path("api/ai/stream/recipe/", api_ai_stream_recipe, name="api_ai_stream_recipe"),

    # Telegram Bot Endpoints
    path("api/telegram/link/", api_telegram_get_link, name="api_telegram_get_link"),
    path("api/telegram/webhook/", api_telegram_webhook, name="api_telegram_webhook"),

    # Legacy server-rendered HTML pages (superseded by the React SPA in /frontend)
    path("legacy/", views.index, name="index"),
    path("legacy/recipe/<int:recipe_id>/", views.recipe_detail, name="recipe_detail"),
    path("legacy/pantry/", views.pantry, name="pantry"),
    path("legacy/can_cook/", views.can_cook, name="can_cook"),
    path("legacy/signup/", views.signup_view, name="signup"),
    path("legacy/login/", views.login_view, name="login"),
    path("legacy/logout/", auth_views.LogoutView.as_view(next_page="/legacy/"), name="logout"),
    path("legacy/ai_suggestions/", views.ai_suggestions, name="ai_suggestions"),
    path("legacy/ai/suggestions/api/", views.ai_suggestions_api, name="ai_suggestions_api"),
    path("legacy/ai/task-status/<str:task_id>/", views.ai_task_status, name="ai_task_status"),
    path("legacy/ai/recipe/<str:name>/", views.ai_recipe_detail, name="ai_recipe_detail"),
]
