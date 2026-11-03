"""The shared dish resolver, ported from the serverless `dish-photos.ts`.

The expected paths deliberately match the TypeScript suite (Appendix A of the
plan), so both apps keep choosing the same photo for the same dish.
"""

import json
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from GetFood import images

ROOT = Path(settings.BASE_DIR)
CATALOG = json.loads((ROOT / "dish-catalog.json").read_text(encoding="utf-8"))


class DishResolverTests(SimpleTestCase):
    def test_prefers_a_specific_dish_over_a_generic_word(self):
        self.assertEqual(images.match_dish_photo("Spaghetti Carbonara"), "recipes/carbonara.jpg")
        self.assertEqual(
            images.match_dish_photo("Creamy Shrimp Alfredo"), "dishes/shrimp_alfredo.webp"
        )
        self.assertEqual(images.match_dish_photo("Lemon Garlic Pasta"), "dishes/spaghetti.webp")

    def test_uses_the_provider_hint_before_a_playful_dish_name(self):
        self.assertEqual(
            images.match_dish_photo("Sunset Skillet Surprise", image_hint="soup"),
            "dishes/lentil_soup.webp",
        )

    def test_falls_back_to_the_cuisine_when_the_name_has_no_keyword(self):
        self.assertEqual(
            images.match_dish_photo("Chef Special", cuisine="Persian"), "dishes/lentil_soup.webp"
        )
        self.assertEqual(
            images.match_dish_photo("Chef Special", cuisine="Italian"),
            "recipes/penne_pomodoro.jpg",
        )

    def test_does_not_confuse_eggplant_with_egg(self):
        self.assertNotEqual(images.match_dish_photo("Roasted Eggplant Salad"), "recipes/omelette.jpg")

    def test_returns_none_for_an_unknown_dish_with_no_cuisine(self):
        self.assertIsNone(images.match_dish_photo("Zorp Surprise"))

    def test_matches_the_catalog_and_keeps_food_groups_sane(self):
        eggplant = images.match_dish_photo("Eggplant Parmigiana")
        self.assertNotEqual(eggplant, "recipes/omelette.jpg")
        groups = {entry.file: entry.group for entry in images.dish_photos()}
        self.assertEqual(groups[eggplant], "veg")

        self.assertEqual(images.match_dish_photo("Menemen"), "recipes/shakshuka.jpg")
        self.assertEqual(images.match_dish_photo("Creamy Shrimp Pasta"), "dishes/shrimp_alfredo.webp")
        self.assertEqual(images.match_dish_photo("Tomato Pasta"), "recipes/penne_pomodoro.jpg")

    def test_uses_the_hint_before_a_localized_name(self):
        groups = {entry.file: entry.group for entry in images.dish_photos()}
        hinted = images.match_dish_photo("Zorp Surprise", image_hint="stew")
        self.assertEqual(groups[hinted], "soup")

        grilled = images.match_dish_photo("طبق غريب", image_hint="grilled chicken")
        self.assertEqual(groups[grilled], "grill")

    def test_matches_persian_and_arabic_names_written_with_variant_letters(self):
        persian = images.match_dish_photo("قرمه سبزی")
        arabic_yeh = images.match_dish_photo("قرمه سبزي")
        self.assertIsNotNone(persian)
        self.assertEqual(arabic_yeh, persian)

        arabic = images.match_dish_photo("قورمة سبزي")
        persian_kaf = images.match_dish_photo("قورمة سبزی")
        self.assertIsNotNone(arabic)
        self.assertEqual(persian_kaf, arabic)


class PickDishPhotoTests(SimpleTestCase):
    def test_is_stable_and_always_returns_a_pool_photo(self):
        first = images.pick_dish_photo("Zorp Surprise")
        self.assertEqual(first, images.pick_dish_photo("Zorp Surprise"))
        self.assertIn(first, images.dish_photo_files())


class AssignDishPhotoTests(SimpleTestCase):
    def test_never_repeats_a_photo_for_different_dishes(self):
        files = images.assign_dish_photo_files(
            [
                {"name": "Pasta One"},
                {"name": "Pasta Two"},
                {"name": "Pasta Three"},
                {"name": "Zorp Surprise"},
            ]
        )
        self.assertEqual(len(set(files)), len(files))

    def test_keeps_the_natural_photo_when_it_is_unique(self):
        self.assertEqual(
            images.assign_dish_photo_files([{"name": "Beef Stew"}, {"name": "Caesar Salad"}]),
            ["dishes/beef.webp", "dishes/caesar.webp"],
        )

    def test_prefers_another_photo_from_the_same_food_group_on_a_collision(self):
        files = images.assign_dish_photo_files(
            [
                {"name": "Lemon Garlic Pasta"},
                {"name": "Tomato Basil Pasta"},
                {"name": "Creamy Mushroom Pasta"},
            ]
        )
        groups = {entry.file: entry.group for entry in images.dish_photos()}
        self.assertEqual(files[0], "dishes/spaghetti.webp")
        self.assertTrue(all(groups[file] == "pasta" for file in files))
        self.assertEqual(len(set(files)), 3)

    def test_reuses_a_same_group_photo_instead_of_rotating_into_another_group(self):
        files = images.assign_dish_photo_files([{"name": f"Pasta {index}"} for index in range(8)])
        groups = {entry.file: entry.group for entry in images.dish_photos()}
        self.assertTrue(all(groups[file] == "pasta" for file in files))


class ImageSetTests(SimpleTestCase):
    def test_every_catalog_file_exists_on_disk(self):
        missing = [
            file["file"]
            for dish in CATALOG["dishes"]
            for file in dish.get("files", [])
            if not (ROOT / "media" / file["file"]).is_file()
        ]
        self.assertEqual(missing, [])

    def test_every_resolver_photo_maps_to_a_manifest_entry_and_a_real_file(self):
        manifest = images._manifest()
        base_files = {entry.file for entry in images.BASE_DISH_PHOTOS}
        problems = []
        for entry in images.dish_photos():
            resolved = images.resolve_image_path(entry.file)
            # Catalog photos already carry their content hash; legacy pool
            # photos must go through the manifest.
            if entry.file in base_files and entry.file not in manifest:
                problems.append(f"{entry.file}: no manifest entry")
            if not (ROOT / "media" / resolved).is_file():
                problems.append(f"{entry.file}: {resolved} is missing")
        self.assertEqual(problems, [])

    def test_every_seed_recipe_and_ingredient_photo_exists(self):
        manifest = images._manifest()
        missing = [
            path
            for path in manifest.values()
            if not (ROOT / "media" / path).is_file()
        ]
        self.assertEqual(missing, [])

    def test_local_image_paths_are_same_origin(self):
        path = images.find_best_image("Shakshuka")
        self.assertTrue(path.startswith("/media/"))
        self.assertNotIn("://", path)
        self.assertTrue((ROOT / "media" / path.removeprefix("/media/")).is_file())

    def test_ingredient_images_are_local_and_fall_back_to_the_placeholder(self):
        garlic = images.find_ingredient_image("Garlic")
        self.assertTrue(garlic.startswith("/media/ingredients/"))
        self.assertTrue((ROOT / "media" / garlic.removeprefix("/media/")).is_file())
        self.assertEqual(images.find_ingredient_image("Zorp Spice"), images.PLACEHOLDER)
