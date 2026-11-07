"""Dish and ingredient photography.

The data comes from the shared ``dish-catalog.json`` (also used by the
serverless app) and the content-hashed files committed under ``media/``. The
resolver mirrors ``packages/shared/src/dish-photos.ts`` so a dish gets the same
photo in both apps:

* haystack precedence: ``image_hint``, then ``name``, then ``cuisine``;
* inside a field the longest whole-word keyword wins, ties keep catalog order;
* Persian/Arabic variants (``ي``/``ی``, ``ك``/``ک``) are unified and diacritics
  are stripped before matching;
* a deterministic hash gives unknown dishes a stable food photo;
* a list-level pass avoids showing the same photo twice.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping

BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "dish-catalog.json"
MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "image-manifest.json"
INGREDIENT_IMAGES_PATH = Path(__file__).resolve().parent / "data" / "ingredient-images.json"
PLACEHOLDER = "/media/placeholder.webp"

USE_BASE_PHOTO = {
    "menemen",
    "shakshuka",
    "spaghetti-carbonara",
    "shrimp-alfredo",
    "caesar-salad",
    "greek-salad",
}

STOP_WORDS = {"and", "with", "the", "a", "al", "la", "de", "of", "in"}


@dataclass(frozen=True)
class DishPhotoEntry:
    file: str
    keywords: tuple[str, ...]
    group: str


# Broad photos kept for unknown dishes and group collisions.
BASE_DISH_PHOTOS: tuple[DishPhotoEntry, ...] = (
    # Pasta and noodles
    DishPhotoEntry("recipes/carbonara.jpg", ("carbonara",), "pasta"),
    DishPhotoEntry(
        "recipes/penne_pomodoro.jpg",
        ("penne", "pomodoro", "arrabbiata", "rigatoni", "fusilli", "tomato pasta"),
        "pasta",
    ),
    DishPhotoEntry(
        "dishes/shrimp_alfredo.webp",
        (
            "shrimp alfredo",
            "prawn alfredo",
            "shrimp pasta",
            "prawn pasta",
            "seafood pasta",
            "creamy pasta",
            "alfredo",
        ),
        "pasta",
    ),
    DishPhotoEntry(
        "dishes/spaghetti.webp",
        ("spaghetti", "pasta", "linguine", "macaroni", "lasagna", "noodle", "noodles", "ramen"),
        "pasta",
    ),
    # Seafood, meat and grills
    DishPhotoEntry("recipes/garlic_shrimp.jpg", ("shrimp", "prawn", "prawns"), "seafood"),
    DishPhotoEntry(
        "dishes/fish_tacos.webp",
        ("fish taco", "fish tacos", "taco", "tacos", "burrito", "wrap", "salsa"),
        "seafood",
    ),
    DishPhotoEntry(
        "dishes/grilled.webp",
        ("grilled", "grill", "barbecue", "bbq", "kebab", "kabob", "skewer", "satay"),
        "grill",
    ),
    DishPhotoEntry(
        "dishes/beef.webp",
        ("steak", "beef", "kofta", "meatball", "meatballs", "meat", "burger"),
        "meat",
    ),
    DishPhotoEntry(
        "dishes/chicken.webp",
        ("roast chicken", "fried chicken", "wings", "drumstick"),
        "meat",
    ),
    DishPhotoEntry(
        "recipes/chicken_skillet.jpg",
        ("chicken", "poultry", "tikka", "shawarma", "tagine"),
        "meat",
    ),
    # Stews, soups and vegetables
    DishPhotoEntry(
        "dishes/lentil_soup.webp",
        ("soup", "stew", "lentil", "dal", "dhal", "broth", "chowder", "ghormeh", "harira"),
        "soup",
    ),
    DishPhotoEntry(
        "dishes/stir_fry.webp",
        (
            "stir fry",
            "stir-fry",
            "stirfry",
            "wok",
            "vegetable",
            "vegetables",
            "veggie",
            "tofu",
            "curry",
        ),
        "veg",
    ),
    DishPhotoEntry(
        "dishes/stuffed_peppers.webp",
        ("stuffed pepper", "stuffed peppers", "bell pepper", "capsicum", "dolma", "dolmeh"),
        "veg",
    ),
    DishPhotoEntry(
        "dishes/potatoes.webp",
        ("potato", "potatoes", "gratin", "fries", "rosti", "hash brown"),
        "veg",
    ),
    # Rice and eggs
    DishPhotoEntry("dishes/risotto.webp", ("risotto",), "rice"),
    DishPhotoEntry(
        "recipes/garlic_fried_rice.jpg",
        ("fried rice", "rice", "pilaf", "pilau", "biryani", "paella"),
        "rice",
    ),
    DishPhotoEntry(
        "recipes/omelette.jpg",
        ("omelette", "omelet", "eggs", "egg", "frittata", "scrambled"),
        "egg",
    ),
    DishPhotoEntry(
        "recipes/shakshuka.jpg",
        ("shakshuka", "poached egg", "menemen"),
        "egg",
    ),
    # Salads, sandwiches and bread
    DishPhotoEntry("dishes/caesar.webp", ("caesar",), "salad"),
    DishPhotoEntry(
        "dishes/greek_salad.webp",
        ("greek salad", "salad", "tabbouleh", "fattoush", "coleslaw", "slaw"),
        "salad",
    ),
    DishPhotoEntry(
        "recipes/avocado_toast.jpg",
        ("avocado", "toast", "bruschetta", "tartine", "crostini"),
        "bread",
    ),
    DishPhotoEntry(
        "recipes/grilled_cheese.jpg",
        ("grilled cheese", "sandwich", "melt", "toastie", "panini"),
        "bread",
    ),
    DishPhotoEntry(
        "dishes/garlic_bread.webp",
        ("garlic bread", "bread", "garlic toast", "focaccia", "baguette"),
        "bread",
    ),
    # Breakfast and sweets
    DishPhotoEntry(
        "recipes/pancakes.jpg",
        ("pancake", "pancakes", "waffle", "waffles", "french toast"),
        "breakfast",
    ),
    DishPhotoEntry(
        "recipes/banana_crepes.jpg",
        ("crepe", "crepes", "palatschinken"),
        "breakfast",
    ),
    DishPhotoEntry(
        "dishes/chocolate.webp",
        (
            "chocolate",
            "cake",
            "brownie",
            "birthday",
            "dessert",
            "tiramisu",
            "cheesecake",
            "pudding",
        ),
        "dessert",
    ),
    DishPhotoEntry(
        "recipes/affogato.jpg",
        ("affogato", "coffee", "espresso", "ice cream", "gelato"),
        "dessert",
    ),
)

CUISINE_PHOTOS = {
    "persian": "dishes/lentil_soup.webp",
    "iranian": "dishes/lentil_soup.webp",
    "turkish": "dishes/grilled.webp",
    "arabic": "dishes/grilled.webp",
    "lebanese": "dishes/greek_salad.webp",
    "mediterranean": "dishes/greek_salad.webp",
    "greek": "dishes/greek_salad.webp",
    "italian": "recipes/penne_pomodoro.jpg",
    "french": "recipes/banana_crepes.jpg",
    "indian": "dishes/stir_fry.webp",
    "pakistani": "dishes/stir_fry.webp",
    "thai": "dishes/stir_fry.webp",
    "chinese": "dishes/stir_fry.webp",
    "japanese": "dishes/stir_fry.webp",
    "korean": "dishes/stir_fry.webp",
    "asian": "dishes/stir_fry.webp",
    "east-asian": "dishes/stir_fry.webp",
    "southeast-asian": "dishes/stir_fry.webp",
    "mexican": "dishes/fish_tacos.webp",
    "spanish": "dishes/shrimp_alfredo.webp",
    "american": "dishes/beef.webp",
    "british": "dishes/potatoes.webp",
    "german": "dishes/potatoes.webp",
    "breakfast": "recipes/pancakes.jpg",
    "dessert": "dishes/chocolate.webp",
}


def normalize_text(value: str) -> str:
    """Lower-case, strip diacritics and unify Persian/Arabic letter variants."""
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    lowered = without_marks.lower()
    return (
        lowered.replace("\u064a", "\u06cc")
        .replace("\u0649", "\u06cc")
        .replace("\u0643", "\u06a9")
        .replace("\u0623", "\u0627")
        .replace("\u0625", "\u0627")
        .replace("\u0622", "\u0627")
        .translate({code: None for code in range(0x064B, 0x0660)})
        .replace("\u0670", "")
        .replace("\u0640", "")
        .replace("\u200c", " ")
        .replace("\u200d", "")
        .replace("_", " ")
    )


def _name_tokens(name: str) -> set[str]:
    return {
        token
        for token in normalize_text(name).split(" ")
        if len(token) >= 3 and token not in STOP_WORDS
    }


def _specific_keywords(dish: Mapping) -> list[str]:
    """Keep catalog keywords that actually describe the dish.

    Translation subagents also emitted broad descriptors ("beef stew", "one
    pot"), which would otherwise hijack every generic request; the base pool
    owns those.
    """
    tokens = _name_tokens(dish["names"]["en"])
    minimum = max(1, len(tokens))
    kept = []
    for raw in dish.get("keywords") or []:
        keyword = normalize_text(raw)
        if len(keyword) < 3:
            continue
        parts = keyword.split(" ")
        if len(parts) < minimum:
            continue
        if not any(part in tokens for part in parts):
            continue
        kept.append(keyword)
    return kept


@lru_cache(maxsize=1)
def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def dish_photos() -> tuple[DishPhotoEntry, ...]:
    entries: list[DishPhotoEntry] = []
    for dish in _catalog().get("dishes", []):
        files = dish.get("files") or []
        photo = files[0].get("file") if files else None
        if not photo or dish.get("key") in USE_BASE_PHOTO:
            continue
        keywords: list[str] = []
        for value in (dish.get("names") or {}).values():
            keyword = normalize_text(value)
            if len(keyword) >= 3:
                keywords.append(keyword)
        keywords.extend(_specific_keywords(dish))
        entries.append(
            DishPhotoEntry(
                file=photo,
                keywords=tuple(keywords),
                group=dish.get("group") or "veg",
            )
        )
    return tuple(entries) + BASE_DISH_PHOTOS


@lru_cache(maxsize=1)
def dish_photo_files() -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for entry in dish_photos():
        seen.setdefault(entry.file, None)
    return tuple(seen)


def _contains_phrase(haystack: str, keyword: str) -> bool:
    # Whole-word, Unicode-aware boundary: ``egg`` must not match ``eggplant``.
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", haystack, re.UNICODE) is not None


@lru_cache(maxsize=1)
def _compiled_keywords() -> tuple[tuple[re.Pattern, str, int], ...]:
    """Whole-word patterns for every keyword, built once.

    ``_best_match`` runs once per serializer field on list endpoints, so it
    must not re-escape and re-compile 4k+ patterns per call (measured ~70 ms
    each, the root cause of the nightly load soak stalling every endpoint).
    """
    return tuple(
        (re.compile(rf"(?<!\w){re.escape(keyword)}(?!\w)", re.UNICODE), entry.file, len(keyword))
        for entry in dish_photos()
        for keyword in entry.keywords
        if len(keyword) >= 3
    )


@lru_cache(maxsize=8192)
def _best_match(field: str) -> str | None:
    haystack = normalize_text(field)
    if not haystack:
        return None
    best_file: str | None = None
    best_length = -1
    for pattern, file, length in _compiled_keywords():
        if pattern.search(haystack) and length > best_length:
            best_file = file
            best_length = length
    return best_file


def _hash(seed: str) -> int:
    """Same 32-bit hash as the JS resolver (``(value * 31 + code) | 0``)."""
    value = 0
    for char in seed:
        value = (value * 31 + ord(char)) & 0xFFFFFFFF
        if value >= 0x80000000:
            value -= 0x100000000
    return abs(value)


def _group_of(path: str) -> str | None:
    for entry in dish_photos():
        if entry.file == path:
            return entry.group
    return None


def match_dish_photo(
    name: str = "",
    image_hint: str | None = None,
    cuisine: str | None = None,
) -> str | None:
    """Best logical photo path for a dish, or ``None`` when nothing matches.

    Pure and deterministic over cached data, so answers are memoized: list
    endpoints ask for the same dish names on every request.
    """
    cache_key = (name or "", (image_hint or "").strip() or None, (cuisine or "").strip() or None)
    return _dish_photo_cached(cache_key)


@lru_cache(maxsize=8192)
def _dish_photo_cached(key: tuple[str, str | None, str | None]) -> str | None:
    name, image_hint, cuisine = key
    if image_hint:
        match = _best_match(image_hint)
        if match:
            return match

    if name:
        match = _best_match(name)
        if match:
            return match

    if cuisine:
        match = _best_match(cuisine)
        if match:
            return match
        normalized = normalize_text(cuisine)
        for cuisine_key, photo in CUISINE_PHOTOS.items():
            if cuisine_key in normalized:
                return photo
    return None


def pick_dish_photo(seed: str) -> str:
    """Stable food photo for a dish with no recognisable keyword."""
    files = dish_photo_files()
    return files[_hash(seed or "dish") % len(files)]


def assign_dish_photo_files(subjects: Iterable[Mapping]) -> list[str]:
    """One photo per dish on a screen, preferring same-group alternatives."""
    used: set[str] = set()
    assigned: list[str] = []

    for subject in subjects:
        name = subject.get("name") or "dish"
        natural = (
            match_dish_photo(
                name=name,
                image_hint=subject.get("image_hint"),
                cuisine=subject.get("cuisine"),
            )
            or pick_dish_photo(name)
        )
        if natural not in used:
            used.add(natural)
            assigned.append(natural)
            continue

        group = _group_of(natural)
        siblings = [
            entry.file
            for entry in dish_photos()
            if entry.group == group and entry.file not in used
        ]
        if siblings:
            choice = siblings[_hash(name) % len(siblings)]
            used.add(choice)
            assigned.append(choice)
        else:
            # Same group exhausted: a duplicate is far better than a photo of a
            # different dish.
            assigned.append(natural)
    return assigned


@lru_cache(maxsize=1)
def _manifest() -> dict[str, str]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def resolve_image_path(path: str) -> str:
    """Map a logical catalog path to the content-hashed file on disk."""
    return _manifest().get(path, path)


def local_media_url(path: str) -> str:
    """A same-origin path (never an absolute URL; the SPA CSP is img-src 'self')."""
    return f"/media/{resolve_image_path(path)}"


def find_best_image(recipe_name: str) -> str:
    """Best local photo for a dish name (kept for existing callers)."""
    match = match_dish_photo(name=recipe_name) if recipe_name else None
    return local_media_url(match or pick_dish_photo(recipe_name or "dish"))


@lru_cache(maxsize=1)
def _ingredient_images() -> dict[str, str]:
    if not INGREDIENT_IMAGES_PATH.exists():
        return {}
    return json.loads(INGREDIENT_IMAGES_PATH.read_text(encoding="utf-8"))


def find_ingredient_image(ingredient_name: str) -> str:
    """Best local photo for an ingredient name (memoized: list endpoints repeat names)."""
    if not ingredient_name:
        return PLACEHOLDER
    return _ingredient_image_cached(ingredient_name.strip())


@lru_cache(maxsize=4096)
def _ingredient_image_cached(ingredient_name: str) -> str:
    images = _ingredient_images()
    if ingredient_name in images:
        return local_media_url(images[ingredient_name])

    lowered = ingredient_name.lower()
    for name, path in images.items():
        if name.lower() == lowered:
            return local_media_url(path)
    for name, path in images.items():
        if lowered and (lowered in name.lower() or name.lower() in lowered):
            return local_media_url(path)
    return PLACEHOLDER


def image_fallback_url(path: str) -> str | None:
    """Public Supabase URL for the same object, used when the local file 404s."""
    from django.conf import settings

    if not path or (path not in _manifest() and path not in _manifest().values()):
        # User uploads are not in the shared buckets; there is no remote copy.
        return None
    resolved = resolve_image_path(path)
    bucket = (
        getattr(settings, "INGREDIENT_IMAGE_BUCKET", "ingredient-images")
        if resolved.startswith("ingredients/")
        else getattr(settings, "IMAGE_BUCKET", "recipe-images")
    )
    base = getattr(settings, "IMAGE_FALLBACK_BASE_URL", "").rstrip("/")
    if not base:
        return None
    return f"{base}/{bucket}/{resolved}"


def subject_image_urls(
    name: str,
    image_hint: str | None = None,
    cuisine: str | None = None,
) -> tuple[str, str | None]:
    """(local image, Supabase fallback) for a dish."""
    logical = match_dish_photo(name=name, image_hint=image_hint, cuisine=cuisine) or pick_dish_photo(
        name or "dish"
    )
    return local_media_url(logical), image_fallback_url(logical)
