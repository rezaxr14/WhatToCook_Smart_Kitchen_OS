"""Backwards-compatible image helpers.

The curated maps that used to live here pointed at Unsplash, which is not
reachable from the deployment target and is blocked by the SPA's strict CSP.
The resolver now lives in :mod:`GetFood.images` and serves the locally bundled,
content-hashed photo set first (with a Supabase fallback URL supplied by the
serializers).
"""

from .images import (  # noqa: F401  (re-exported for existing callers)
    PLACEHOLDER,
    find_best_image,
    find_ingredient_image,
    image_fallback_url,
    local_media_url,
    match_dish_photo,
    resolve_image_path,
    subject_image_urls,
)

DEFAULT_FALLBACK_IMAGE = PLACEHOLDER
DEFAULT_INGREDIENT_IMAGE = PLACEHOLDER
