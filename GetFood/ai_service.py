import base64
import json
import logging
import os
import re
import requests
from django.conf import settings
from . import ai_cache
from .utils import find_best_image

logger = logging.getLogger(__name__)

# Config from settings or environment
GEMINI_API_KEY = getattr(settings, "GEMINI_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = getattr(settings, "GEMINI_MODEL", "gemini-3.5-flash-lite") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
LMSTUDIO_URL = getattr(settings, "LMSTUDIO_URL", "http://host.docker.internal:1234/v1/chat/completions")
MODEL_NAME = getattr(settings, "MODEL_NAME", "llama-3.2-3b-instruct")
DEFAULT_AI_PROVIDER = getattr(settings, "AI_PROVIDER", "gemini")

# Canonical order of fallback free-tier Flash models with generous token quotas prioritized
GEMINI_FALLBACK_MODELS = [
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


def _is_rate_limit_error(error_msg: str) -> bool:
    """Detect if an exception or response corresponds to a 429 / quota limit."""
    err_lower = str(error_msg).lower()
    return any(
        kw in err_lower
        for kw in [
            "429",
            "quota",
            "resource_exhausted",
            "resourceexhausted",
            "rate limit",
            "ratelimit",
            "exceeded your current quota",
            "too many requests",
        ]
    )


# Human languages the AI can be instructed to answer in (mirrors the SPA i18n set).
AI_RESPONSE_LANGUAGES = {
    "en": "English",
    "tr": "Turkish",
    "fa": "Persian (Farsi)",
    "ar": "Arabic",
    "es": "Spanish",
}


def normalize_language(language: str = None) -> str | None:
    """Normalize a BCP-47-ish tag ('fa-IR', 'en-US') to a supported base code."""
    if not language:
        return None
    code = str(language).split("-")[0].strip().lower()
    return code if code in AI_RESPONSE_LANGUAGES else None


def _language_instruction(language: str = None) -> str:
    """
    Strict directive forcing all human-readable output into the user's UI language.
    JSON keys stay English so downstream parsing is unaffected.
    """
    code = normalize_language(language)
    if not code or code == "en":
        return ""
    lang_name = AI_RESPONSE_LANGUAGES[code]
    return (
        f"LANGUAGE REQUIREMENT: You MUST respond entirely in {lang_name}. "
        f"Write ALL human-readable text (titles, dish names, descriptions, steps, tips, "
        f"quantities, categories) in {lang_name}. For JSON outputs keep the JSON keys "
        f"exactly as specified (English keys) but every string VALUE must be written "
        f"in {lang_name}. Do not mix English words into the values."
    )


def _apply_language(system_instruction: str, language: str = None) -> str:
    """Merge the language directive into any system instruction."""
    parts = [p.strip() for p in [system_instruction, _language_instruction(language)] if p and p.strip()]
    return " ".join(parts)


def _call_gemini_with_meta(
    prompt: str,
    system_instruction: str = "",
    model: str = None,
    response_mime_type: str = "application/json",
) -> tuple[str, str, list[str]]:
    """
    Call Google AI Studio Gemini API with resilient multi-model fallback and quota tracking.
    Returns:
        (generated_text, model_used, rate_limited_models)
    """
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in .env or settings.")

    # Build prioritized model candidate list
    candidate_models = []
    if model and model.strip():
        candidate_models.append(model.strip())
    if GEMINI_MODEL and GEMINI_MODEL not in candidate_models:
        candidate_models.append(GEMINI_MODEL)

    for fallback_m in GEMINI_FALLBACK_MODELS:
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    rate_limited_models = []
    last_err = None

    # 1. Try google.genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        for candidate in candidate_models:
            try:
                config_kwargs = {
                    "temperature": 0.7,
                    "system_instruction": system_instruction if system_instruction else None,
                }
                if response_mime_type:
                    config_kwargs["response_mime_type"] = response_mime_type

                config = types.GenerateContentConfig(**config_kwargs)
                resp = client.models.generate_content(
                    model=candidate,
                    contents=prompt,
                    config=config,
                )
                if resp and resp.text:
                    return resp.text.strip(), candidate, rate_limited_models
            except Exception as ex:
                ex_str = str(ex)
                if _is_rate_limit_error(ex_str):
                    logger.warning("Gemini model '%s' hit rate/quota limit: %s", candidate, ex)
                    if candidate not in rate_limited_models:
                        rate_limited_models.append(candidate)
                else:
                    logger.warning("Gemini SDK attempt with model '%s' failed: %s", candidate, ex)
                last_err = ex
                continue
    except ImportError:
        pass

    # 2. REST API Fallback
    for candidate in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={api_key}"
            gen_config = {"temperature": 0.7}
            if response_mime_type:
                gen_config["responseMimeType"] = response_mime_type

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": gen_config,
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    if text:
                        return text, candidate, rate_limited_models
            elif response.status_code == 429 or _is_rate_limit_error(response.text):
                logger.warning("Gemini REST model '%s' received 429 / quota limit", candidate)
                if candidate not in rate_limited_models:
                    rate_limited_models.append(candidate)
            else:
                logger.warning("Gemini REST model '%s' failed with status %s: %s", candidate, response.status_code, response.text)
        except Exception as ex:
            if _is_rate_limit_error(str(ex)):
                if candidate not in rate_limited_models:
                    rate_limited_models.append(candidate)
            logger.warning("Gemini REST attempt with model '%s' failed: %s", candidate, ex)
            last_err = ex
            continue

    raise ValueError(f"All Gemini models failed. Last error: {last_err}")


def _call_gemini(
    prompt: str,
    system_instruction: str = "",
    model: str = None,
    response_mime_type: str = "application/json",
) -> str:
    """Convenience wrapper that returns generated text."""
    text, _, _ = _call_gemini_with_meta(
        prompt,
        system_instruction=system_instruction,
        model=model,
        response_mime_type=response_mime_type,
    )
    return text


def _call_gemini_vision(
    prompt: str,
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    system_instruction: str = "",
) -> str:
    """
    Multimodal Gemini call (text + image) with the same resilient
    multi-model fallback strategy as the text-only path.
    """
    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in .env or settings.")
    if not image_bytes:
        raise ValueError("No image data supplied for vision analysis.")

    candidate_models = []
    if GEMINI_MODEL and GEMINI_MODEL not in candidate_models:
        candidate_models.append(GEMINI_MODEL)
    for fallback_m in GEMINI_FALLBACK_MODELS:
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    last_err = None

    # 1. Try google.genai SDK
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        for candidate in candidate_models:
            try:
                config = types.GenerateContentConfig(
                    temperature=0.4,
                    system_instruction=system_instruction if system_instruction else None,
                )
                resp = client.models.generate_content(
                    model=candidate,
                    contents=[
                        prompt,
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                    ],
                    config=config,
                )
                if resp and resp.text:
                    return resp.text.strip()
            except Exception as ex:
                logger.warning("Gemini Vision SDK attempt with model '%s' failed: %s", candidate, ex)
                last_err = ex
                continue
    except ImportError:
        pass

    # 2. REST API Fallback
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    for candidate in candidate_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{candidate}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt},
                            {"inline_data": {"mime_type": mime_type, "data": encoded}},
                        ]
                    }
                ],
                "generationConfig": {"temperature": 0.4},
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=45,
            )

            if response.status_code == 200:
                data = response.json()
                candidates = data.get("candidates", [])
                if candidates:
                    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                    if text:
                        return text
            else:
                logger.warning("Gemini Vision REST model '%s' failed with status %s", candidate, response.status_code)
        except Exception as ex:
            logger.warning("Gemini Vision REST attempt with model '%s' failed: %s", candidate, ex)
            last_err = ex
            continue

    raise ValueError(f"All Gemini vision models failed. Last error: {last_err}")



def _call_lmstudio(prompt: str, system_instruction: str = "") -> str:
    """Call local LM Studio OpenAI-compatible endpoint."""
    messages = []
    if system_instruction:
        messages.append({"role": "system", "content": system_instruction})
    messages.append({"role": "user", "content": prompt})

    response = requests.post(
        LMSTUDIO_URL,
        headers={"Content-Type": "application/json"},
        json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    return content


def _clean_json_str(content: str) -> str:
    """Remove markdown ticks or stray formatting."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```[a-zA-Z]*\n?", "", content)
        content = re.sub(r"```$", "", content).strip()
    return content


def _fallback_recipe_suggestions(ingredients: list[str]) -> list[dict]:
    """Graceful culinary fallback suggestions when live AI is offline."""
    ing_set = [i.lower() for i in ingredients]
    
    presets = [
        {
            "name": "Savory Chef's Skillet",
            "short_description": f"A vibrant and aromatic stir skillet celebrating fresh {', '.join(ingredients[:3])}.",
            "cuisine": "Fusion",
            "difficulty": "Easy",
            "image_hint": "stir_fry",
            "prep_time": "20 mins"
        },
        {
            "name": "Rustic Garden Bowl",
            "short_description": "Wholesome, pan-seared bowl seasoned to perfection with rich flavors.",
            "cuisine": "Mediterranean",
            "difficulty": "Easy",
            "image_hint": "salad",
            "prep_time": "15 mins"
        },
        {
            "name": "Hearty Comfort Stew",
            "short_description": "Slow-simmered rich stew infused with deep savory herbs.",
            "cuisine": "Homestyle",
            "difficulty": "Medium",
            "image_hint": "stew",
            "prep_time": "35 mins"
        },
        {
            "name": "Crispy Pan Frittata",
            "short_description": "Golden pan-baked delight binding tender ingredients with fluffy eggs and seasoning.",
            "cuisine": "Italian",
            "difficulty": "Easy",
            "image_hint": "omelette",
            "prep_time": "18 mins"
        },
        {
            "name": "Gourmet Pasta Supreme",
            "short_description": "Silky, garlic-kissed pasta tossed with caramelized ingredients.",
            "cuisine": "Italian",
            "difficulty": "Medium",
            "image_hint": "spaghetti",
            "prep_time": "25 mins"
        }
    ]
    return presets


def generate_recipe_suggestions_meta(ingredients: list[str], provider: str = None, model: str = None, language: str = None) -> tuple[list[dict], str, list[str]]:
    """Generate 4-6 recipe ideas from pantry ingredients with model usage metadata."""
    if not provider:
        provider = DEFAULT_AI_PROVIDER

    prompt = (
        f"You are a master creative chef. Based on these available pantry ingredients: {', '.join(ingredients)}, "
        "suggest 5 realistic, enticing, and distinct dishes that can be cooked. "
        "Return ONLY a JSON array with objects containing: "
        "'name' (str), 'short_description' (str), 'cuisine' (str), 'difficulty' (Easy/Medium/Hard), "
        "'prep_time' (e.g. '25 mins'), 'image_hint' (e.g. 'pasta', 'chicken', 'salad', 'soup')."
    )
    system_instruction = _apply_language(
        "You are a professional culinary chef. Always respond with clean, valid JSON without markdown formatting.",
        language,
    )

    content = ""
    model_used = model or (GEMINI_MODEL if provider == "gemini" else MODEL_NAME)
    rate_limited_models = []
    error_note = None

    try:
        if provider == "gemini":
            content, model_used, rate_limited_models = _call_gemini_with_meta(prompt, system_instruction, model=model)
        elif provider == "lmstudio":
            content = _call_lmstudio(prompt, system_instruction)
            model_used = MODEL_NAME
        else:
            # Try Gemini first, then LM Studio
            try:
                content, model_used, rate_limited_models = _call_gemini_with_meta(prompt, system_instruction, model=model)
            except Exception:
                content = _call_lmstudio(prompt, system_instruction)
                model_used = MODEL_NAME
    except Exception as e:
        logger.warning(f"AI Provider ({provider}) failed: {e}. Using fallback culinary recipes.")
        error_note = str(e)

    recipes = []
    if content:
        cleaned = _clean_json_str(content)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "dishes" in parsed:
                recipes = parsed["dishes"]
            elif isinstance(parsed, dict) and "recipes" in parsed:
                recipes = parsed["recipes"]
            elif isinstance(parsed, list):
                recipes = parsed
        except json.JSONDecodeError:
            matches = re.findall(r"\{.*?\}", cleaned, re.DOTALL)
            for m in matches:
                try:
                    obj = json.loads(m)
                    if "name" in obj:
                        recipes.append(obj)
                except Exception:
                    continue

    if not recipes:
        recipes = _fallback_recipe_suggestions(ingredients)

    # Attach best matching local images
    for r in recipes:
        r["image"] = find_best_image(r.get("name", "dish"))
        if "provider" not in r:
            r["provider"] = provider if not error_note else "fallback (AI offline)"
        r["model_used"] = model_used

    return recipes, model_used, rate_limited_models


def generate_recipe_suggestions(ingredients: list[str], provider: str = None, model: str = None, language: str = None) -> list[dict]:
    """Generate 4-6 recipe ideas from pantry ingredients (backward compatible wrapper)."""
    recipes, _, _ = generate_recipe_suggestions_meta(ingredients, provider=provider, model=model, language=language)
    return recipes


def generate_recipe_detail_meta(recipe_name: str, provider: str = None, model: str = None, language: str = None) -> tuple[dict, str, list[str]]:
    """Generate detailed step-by-step cooking guide with ingredients, instructions, and model metadata."""
    if not provider:
        provider = DEFAULT_AI_PROVIDER

    cache_key = ai_cache.detail_key(recipe_name, provider, model, normalize_language(language))
    cached = ai_cache.get_detail(cache_key)
    if cached:
        return cached, cached.get("model_used") or model, cached.get("rate_limited_models") or []

    prompt = (
        f"You are a Michelin-star master chef. Provide a comprehensive cooking recipe for '{recipe_name}'. "
        "Return valid JSON with the following exact keys:\n"
        "- 'name': string\n"
        "- 'description': mouthwatering 2-3 sentence overview\n"
        "- 'cuisine': string (e.g. Italian, Asian, Mexican)\n"
        "- 'difficulty': 'Easy' | 'Medium' | 'Hard'\n"
        "- 'time_minutes': integer (total cooking time in minutes)\n"
        "- 'ingredients': list of objects, each with {'name': string, 'amount': string, 'unit': string}\n"
        "- 'instructions': list of objects, each with {'step': string, 'time_minutes': integer or null, 'chef_tip': string or null}\n"
        "- 'nutrition': object with {'calories': string, 'protein': string, 'carbs': string, 'fat': string}\n"
        "Return ONLY raw JSON, no markdown formatting."
    )
    system_instruction = _apply_language(
        "You are a professional chef. Always output valid structured JSON without markdown wrappers.",
        language,
    )

    content = ""
    model_used = model or (GEMINI_MODEL if provider == "gemini" else MODEL_NAME)
    rate_limited_models = []

    try:
        if provider == "gemini":
            content, model_used, rate_limited_models = _call_gemini_with_meta(prompt, system_instruction, model=model)
        elif provider == "lmstudio":
            content = _call_lmstudio(prompt, system_instruction)
            model_used = MODEL_NAME
        else:
            try:
                content, model_used, rate_limited_models = _call_gemini_with_meta(prompt, system_instruction, model=model)
            except Exception:
                content = _call_lmstudio(prompt, system_instruction)
                model_used = MODEL_NAME
    except Exception as e:
        logger.warning(f"AI Detail fetch failed for '{recipe_name}': {e}")

    recipe_data = None
    if content:
        cleaned = _clean_json_str(content)
        try:
            recipe_data = json.loads(cleaned)
        except json.JSONDecodeError:
            try:
                recipe_data = json.loads(cleaned.encode('utf-8').decode('unicode_escape'))
            except Exception:
                recipe_data = None

    used_fallback = False
    if not recipe_data or not isinstance(recipe_data, dict) or "ingredients" not in recipe_data:
        # Fallback recipe detail
        used_fallback = True
        recipe_data = {
            "name": recipe_name,
            "description": f"A delightful and flavorful chef-crafted recipe for {recipe_name}, balanced with fresh aromatics and rich seasonings.",
            "cuisine": "Gourmet",
            "difficulty": "Medium",
            "time_minutes": 30,
            "ingredients": [
                {"name": "Main Ingredients (Pantry Blend)", "amount": "300", "unit": "g"},
                {"name": "Olive Oil or Butter", "amount": "2", "unit": "tbsp"},
                {"name": "Garlic / Aromatics", "amount": "2", "unit": "cloves"},
                {"name": "Sea Salt & Black Pepper", "amount": "1", "unit": "pinch"},
                {"name": "Fresh Herbs for Garnish", "amount": "1", "unit": "handful"}
            ],
            "instructions": [
                {
                    "step": "Prep and clean all ingredients. Dice aromatics finely and season proteins/vegetables lightly.",
                    "time_minutes": 5,
                    "chef_tip": "Mise en place ensures everything cooks evenly without burning."
                },
                {
                    "step": "Warm pan with oil over medium heat. Sauté aromatics for 1-2 minutes until fragrance blooms.",
                    "time_minutes": 3,
                    "chef_tip": "Keep heat controlled to prevent burning garlic."
                },
                {
                    "step": "Add core ingredients and cook thoroughly until nicely browned and caramelized.",
                    "time_minutes": 15,
                    "chef_tip": "Do not overcrowd the pan for better browning."
                },
                {
                    "step": "Garnish with fresh chopped herbs, finish with flaky sea salt and serve immediately.",
                    "time_minutes": 2,
                    "chef_tip": "A squeeze of fresh lemon brings all flavors together."
                }
            ],
            "nutrition": {
                "calories": "380 kcal",
                "protein": "22g",
                "carbs": "35g",
                "fat": "14g"
            }
        }

    recipe_data["image"] = find_best_image(recipe_name)
    recipe_data["provider"] = provider
    recipe_data["model_used"] = model_used
    recipe_data["rate_limited_models"] = rate_limited_models
    if not used_fallback:  # never pin a degraded answer in Redis for 24h
        ai_cache.set_detail(cache_key, recipe_data)
    return recipe_data, model_used, rate_limited_models


def generate_recipe_detail(recipe_name: str, provider: str = None, model: str = None, language: str = None) -> dict:
    """Generate detailed step-by-step cooking guide (backward compatible wrapper)."""
    data, _, _ = generate_recipe_detail_meta(recipe_name, provider=provider, model=model, language=language)
    return data


def _fallback_fridge_scan() -> list[dict]:
    """Fallback detected grocery items when AI Vision is offline or processing mock."""
    return [
        {"name": "Eggs", "category": "Dairy & Eggs", "confidence": 0.96, "estimated_quantity": "1 carton (12 pcs)"},
        {"name": "Milk", "category": "Dairy & Eggs", "confidence": 0.94, "estimated_quantity": "1 bottle"},
        {"name": "Tomato", "category": "Produce", "confidence": 0.91, "estimated_quantity": "4 pieces"},
        {"name": "Cheddar Cheese", "category": "Dairy & Eggs", "confidence": 0.89, "estimated_quantity": "1 block"},
        {"name": "Butter", "category": "Dairy & Eggs", "confidence": 0.88, "estimated_quantity": "1 pack"},
        {"name": "Garlic", "category": "Produce", "confidence": 0.86, "estimated_quantity": "2 bulbs"},
        {"name": "Onion", "category": "Produce", "confidence": 0.85, "estimated_quantity": "3 pieces"},
        {"name": "Bell Pepper", "category": "Produce", "confidence": 0.82, "estimated_quantity": "2 pieces"},
        {"name": "Chicken Breast", "category": "Meat & Seafood", "confidence": 0.80, "estimated_quantity": "500g package"}
    ]


def scan_fridge_image(image_bytes: bytes, mime_type: str = "image/jpeg", provider: str = None, language: str = None) -> list[dict]:
    """
    Analyze image of a fridge/pantry/groceries using Gemini Vision.
    Returns structured list of detected ingredients.
    'name' stays canonical English (safe for DB + recipe matching);
    'display_name' is the localized label when a non-English UI language is set.
    """
    if not provider:
        provider = DEFAULT_AI_PROVIDER

    lang_code = normalize_language(language)
    display_name_rule = ""
    system_instruction = _apply_language(
        "You are an expert culinary AI and kitchen computer vision assistant. Always respond with clean, valid JSON.",
        language,
    )
    if lang_code and lang_code != "en":
        display_name_rule = (
            f"\n- 'display_name': the same ingredient name translated into {AI_RESPONSE_LANGUAGES[lang_code]} "
            "(this is what the user sees in their UI)"
        )

    prompt = (
        "You are an expert culinary AI and kitchen computer vision assistant. "
        "Analyze this image of a refrigerator, kitchen pantry, grocery haul, or countertop. "
        "Identify all visible food ingredients, fresh produce, dairy, meats, seasonings, condiments, and groceries. "
        "Return ONLY a clean JSON array with objects containing:\n"
        "- 'name': standardized singular ingredient name in English Title Case (e.g. 'Egg', 'Tomato', 'Cheddar Cheese', 'Milk', 'Bell Pepper', 'Garlic', 'Chicken Breast', 'Avocado', 'Butter', 'Onion', 'Lemon')\n"
        f"- 'category': one of ['Produce', 'Dairy & Eggs', 'Meat & Seafood', 'Grains & Pasta', 'Pantry & Spices', 'Condiments', 'Bakery', 'Beverage', 'Other']{display_name_rule}\n"
        "- 'confidence': float between 0.0 and 1.0 (estimated confidence of detection)\n"
        "- 'estimated_quantity': string or null (e.g. '6 eggs', '2 bottles', '1 bag')\n"
        "The 'name' field MUST always be in English regardless of any other language requirement. "
        "Return ONLY the JSON array, no conversational text or markdown code blocks."
    )

    detected_items = []
    content = ""

    try:
        if provider == "gemini":
            content = _call_gemini_vision(prompt, image_bytes, mime_type=mime_type, system_instruction=system_instruction)
        else:
            # If provider is not gemini, attempt gemini vision or fallback
            content = _call_gemini_vision(prompt, image_bytes, mime_type=mime_type, system_instruction=system_instruction)
    except Exception as e:
        logger.warning(f"Gemini Vision scan encountered issue: {e}. Utilizing culinary vision fallback.")

    if content:
        cleaned = _clean_json_str(content)
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "detected_ingredients" in parsed:
                detected_items = parsed["detected_ingredients"]
            elif isinstance(parsed, dict) and "ingredients" in parsed:
                detected_items = parsed["ingredients"]
            elif isinstance(parsed, list):
                detected_items = parsed
        except json.JSONDecodeError:
            matches = re.findall(r"\{.*?\}", cleaned, re.DOTALL)
            for m in matches:
                try:
                    obj = json.loads(m)
                    if "name" in obj:
                        detected_items.append(obj)
                except Exception:
                    continue

    if not detected_items:
        detected_items = _fallback_fridge_scan()

    # Format and sanitize
    sanitized = []
    for item in detected_items:
        if isinstance(item, dict) and item.get("name"):
            name = item["name"].strip().title()
            entry = {
                "name": name,
                "category": item.get("category", "Produce"),
                "confidence": float(item.get("confidence", 0.9)),
                "estimated_quantity": item.get("estimated_quantity"),
            }
            display_name = str(item.get("display_name") or "").strip()
            if display_name:
                entry["display_name"] = display_name
            sanitized.append(entry)

    return sanitized


def stream_recipe_generation(recipe_name: str, provider: str = None, language: str = None):
    """
    Stream live recipe generation token-by-token using Server-Sent Events (SSE).
    Yields SSE formatted chunks: 'data: {"chunk": "..."}\n\n'
    """
    if not provider:
        provider = DEFAULT_AI_PROVIDER

    prompt = (
        f"You are a Michelin-star master chef. Provide a step-by-step gourmet recipe for '{recipe_name}'. "
        "Include a description, cooking time, ingredients with measurements, sequential numbered cooking steps with chef tips, "
        "and a calorie & macro estimate. Format cleanly."
    )
    system_instruction = _apply_language(
        "You are a Michelin-star master chef writing a beautiful, clearly formatted recipe.",
        language,
    )

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")

    if provider == "gemini" and api_key:
        try:
            model = GEMINI_MODEL
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.7},
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            with requests.post(url, json=payload, headers={"Content-Type": "application/json"}, stream=True, timeout=60) as resp:
                if resp.status_code == 200:
                    for line in resp.iter_lines():
                        if line:
                            decoded = line.decode("utf-8")
                            if decoded.startswith("data: "):
                                data_str = decoded[6:]
                                try:
                                    parsed = json.loads(data_str)
                                    text_chunk = (
                                        parsed.get("candidates", [{}])[0]
                                        .get("content", {})
                                        .get("parts", [{}])[0]
                                        .get("text", "")
                                    )
                                    if text_chunk:
                                        yield f"data: {json.dumps({'chunk': text_chunk, 'done': False})}\n\n"
                                except Exception:
                                    continue
                    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"
                    return
        except Exception as e:
            logger.warning(f"Live Gemini stream failed: {e}. Switching to culinary fallback streamer.")

    # Graceful fallback live streaming simulation
    fallback_text = (
        f"# Gourmet {recipe_name}\n\n"
        f"**Preparation Time:** 25 mins | **Difficulty:** Medium | **Servings:** 4\n\n"
        f"### 🌿 Ingredients\n"
        f"- 400g Fresh Main Ingredients (Pantry Selection)\n"
        f"- 2 tbsp Extra Virgin Olive Oil\n"
        f"- 3 cloves Fresh Garlic, minced\n"
        f"- 1 tsp Sea Salt & Fresh Cracked Black Pepper\n"
        f"- Handful of fresh garden herbs (Parsley or Basil)\n\n"
        f"### 👨‍🍳 Cooking Instructions\n"
        f"1. **Prep & Clean:** Wash and dice all aromatics. Season ingredients evenly for consistent flavor absorption.\n"
        f"2. **Preheat Pan:** Heat skillet over medium-high until shimmering oil coats the surface.\n"
        f"3. **Sauté Aromatics:** Fry garlic and herbs for 90 seconds until golden and aromatic.\n"
        f"4. **Caramelize Main Ingredients:** Introduce pantry ingredients and sear for 10-12 minutes without overcrowding.\n"
        f"5. **Meld & Rest:** Reduce heat to simmer for 5 minutes, let rest 2 minutes before serving hot.\n\n"
        f"### 🥗 Nutrition\n"
        f"**Calories:** ~380 kcal | **Protein:** 24g | **Carbs:** 32g | **Fat:** 12g\n"
    )

    import time
    words = fallback_text.split(" ")
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
        time.sleep(0.03)

    yield f"data: {json.dumps({'chunk': '', 'done': True})}\n\n"


def ask_recipe_chat(
    recipe_name: str,
    ingredients: list | str = None,
    instructions: list | str = None,
    user_question: str = "",
    history: list[dict] = None,
    provider: str = "gemini",
    model: str = None,
    language: str = None,
) -> dict:
    """
    Interactive AI Sous-Chef Chat Q&A tailored specifically to a dish.
    Answers substitutions, wine pairings, heat adjustments, equipment queries, leftovers, etc.
    """
    if not provider:
        provider = DEFAULT_AI_PROVIDER

    ing_str = json.dumps(ingredients) if isinstance(ingredients, (list, dict)) else str(ingredients or "")
    inst_str = json.dumps(instructions) if isinstance(instructions, (list, dict)) else str(instructions or "")

    system_instruction = _apply_language(
        f"You are the AI Executive Sous-Chef for the recipe '{recipe_name}'.\n"
        f"Recipe Context:\n"
        f"- Ingredients: {ing_str}\n"
        f"- Steps/Instructions: {inst_str}\n\n"
        "Your role: Warmly, concisely, and expertly answer the home cook's questions about this specific recipe.\n"
        "Guide them on ingredient substitutions, flavor boosts, cooking techniques, wine/beverage pairings, "
        "dietary conversions (vegan, keto, gluten-free), air-fryer/instant pot adaptations, storage tips, or heat levels.\n"
        "Keep answers helpful, engaging, culinary-sound, and formatted nicely with markdown bullet points if listing steps or items.",
        language,
    )

    # Build conversation context
    conversation_prompt = ""
    if history and isinstance(history, list):
        for msg in history[-6:]:  # Keep recent history
            role = "Cook" if msg.get("role") in ["user", "human"] else "Chef"
            conversation_prompt += f"{role}: {msg.get('content', '')}\n"

    conversation_prompt += f"Cook: {user_question}\nChef:"

    reply = ""
    model_used = model or GEMINI_MODEL
    rate_limited_models = []

    try:
        if provider == "gemini":
            reply, model_used, rate_limited_models = _call_gemini_with_meta(
                conversation_prompt,
                system_instruction=system_instruction,
                model=model,
                response_mime_type="",  # Plain text response
            )
        elif provider == "lmstudio":
            reply = _call_lmstudio(conversation_prompt, system_instruction=system_instruction)
            model_used = MODEL_NAME
        else:
            try:
                reply, model_used, rate_limited_models = _call_gemini_with_meta(
                    conversation_prompt,
                    system_instruction=system_instruction,
                    model=model,
                    response_mime_type="",
                )
            except Exception:
                reply = _call_lmstudio(conversation_prompt, system_instruction=system_instruction)
                model_used = MODEL_NAME
    except Exception as e:
        logger.warning(f"Recipe Chat AI failed for '{recipe_name}': {e}")
        # Friendly fallback answer
        reply = (
            f"As your sous-chef for **{recipe_name}**, here are some top tips:\n\n"
            f"- **Substitutions:** If missing an ingredient, swap with similar flavor profiles (e.g., butter for olive oil, Greek yogurt for sour cream).\n"
            f"- **Flavor Boost:** A splash of fresh lemon juice, a pinch of sea salt, or fresh cracked black pepper right before serving will brighten the dish.\n"
            f"- **Storage:** Store leftovers in an airtight container in the fridge for up to 3 days. Reheat gently to preserve texture."
        )

    return {
        "reply": reply.strip(),
        "model_used": model_used,
        "rate_limited_models": rate_limited_models,
        "recipe_name": recipe_name,
    }

