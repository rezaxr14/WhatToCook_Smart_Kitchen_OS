from django.core.management.base import BaseCommand
from GetFood.models import Ingredient, Recipe, RecipeIngredient

FULL_INGREDIENT_CATALOG = [
    # Produce (Vegetables, Fruits, Herbs)
    ("Garlic", "Produce", 149),
    ("Onion", "Produce", 40),
    ("Tomato", "Produce", 18),
    ("Potato", "Produce", 77),
    ("Avocado", "Produce", 160),
    ("Spinach", "Produce", 23),
    ("Broccoli", "Produce", 34),
    ("Mushrooms", "Produce", 22),
    ("Bell Pepper", "Produce", 31),
    ("Carrot", "Produce", 41),
    ("Cucumber", "Produce", 15),
    ("Lemon", "Produce", 29),
    ("Lime", "Produce", 30),
    ("Fresh Basil", "Produce", 23),
    ("Ginger", "Produce", 80),
    ("Chili Pepper", "Produce", 40),
    ("Zucchini", "Produce", 17),
    ("Cilantro", "Produce", 23),
    ("Green Onion", "Produce", 32),
    ("Lettuce", "Produce", 15),
    ("Celery", "Produce", 16),
    ("Banana", "Produce", 89),
    ("Strawberries", "Produce", 32),
    ("Blueberries", "Produce", 57),
    ("Apple", "Produce", 52),

    # Dairy & Eggs & Frozen
    ("Eggs", "Dairy & Eggs", 155),
    ("Milk", "Dairy & Eggs", 42),
    ("Butter", "Dairy & Eggs", 717),
    ("Cheddar Cheese", "Dairy & Eggs", 402),
    ("Parmesan", "Dairy & Eggs", 431),
    ("Mozzarella", "Dairy & Eggs", 280),
    ("Feta Cheese", "Dairy & Eggs", 264),
    ("Heavy Cream", "Dairy & Eggs", 340),
    ("Greek Yogurt", "Dairy & Eggs", 59),
    ("Sour Cream", "Dairy & Eggs", 193),
    ("Vanilla Ice Cream", "Dairy & Eggs", 207),
    ("Chocolate Ice Cream", "Dairy & Eggs", 216),
    ("Cream Cheese", "Dairy & Eggs", 342),

    # Meat & Seafood & Proteins
    ("Chicken Breast", "Meat & Seafood", 165),
    ("Chicken Thighs", "Meat & Seafood", 209),
    ("Ground Beef", "Meat & Seafood", 250),
    ("Beef Steak", "Meat & Seafood", 271),
    ("Bacon", "Meat & Seafood", 541),
    ("Salmon Fillet", "Meat & Seafood", 208),
    ("Shrimp", "Meat & Seafood", 99),
    ("Canned Tuna", "Meat & Seafood", 116),
    ("Pork Chop", "Meat & Seafood", 231),
    ("Tofu", "Meat & Seafood", 76),
    ("Ham", "Meat & Seafood", 145),

    # Grains & Bakery & Pasta
    ("Bread", "Grains & Pasta", 265),
    ("Sourdough Bread", "Grains & Pasta", 240),
    ("Pasta", "Grains & Pasta", 131),
    ("Spaghetti", "Grains & Pasta", 158),
    ("Rice", "Grains & Pasta", 130),
    ("Jasmine Rice", "Grains & Pasta", 130),
    ("Flour", "Grains & Pasta", 364),
    ("Rolled Oats", "Grains & Pasta", 389),
    ("Tortillas", "Grains & Pasta", 237),
    ("Burger Buns", "Grains & Pasta", 270),
    ("Noodles", "Grains & Pasta", 138),
    ("Quinoa", "Grains & Pasta", 120),

    # Pantry & Spices & Condiments
    ("Olive Oil", "Pantry & Spices", 884),
    ("Vegetable Oil", "Pantry & Spices", 884),
    ("Tomato Sauce", "Pantry & Spices", 29),
    ("Soy Sauce", "Pantry & Spices", 53),
    ("Honey", "Pantry & Spices", 304),
    ("Sugar", "Pantry & Spices", 387),
    ("Salt", "Pantry & Spices", 0),
    ("Black Pepper", "Pantry & Spices", 251),
    ("Red Pepper Flakes", "Pantry & Spices", 318),
    ("Oregano", "Pantry & Spices", 265),
    ("Cinnamon", "Pantry & Spices", 247),
    ("Vanilla Extract", "Pantry & Spices", 288),
    ("Maple Syrup", "Pantry & Spices", 260),
    ("Mustard", "Pantry & Spices", 66),
    ("Mayonnaise", "Pantry & Spices", 680),
    ("Ketchup", "Pantry & Spices", 112),
    ("Peanut Butter", "Pantry & Spices", 588),
    ("Cocoa Powder", "Pantry & Spices", 228),
    ("Baking Powder", "Pantry & Spices", 53),
]

RECIPE_CATALOG = [
    {
        "name": "Artisan Garlic Butter Grilled Cheese",
        "description": "Crispy golden sourdough crust infused with crushed garlic herb butter and molten sharp cheddar core.",
        "cooking_time": 15,
        "instructions": "1. Spread garlic butter generously on outer sourdough slices.\n2. Layer thick sharp cheddar slices inside.\n3. Toast in a heavy skillet over medium-low heat until deep amber crisp and cheese stretches beautifully.\n4. Slice diagonally and serve steaming hot.",
        "ingredients": [
            ("Bread", "Grains & Pasta", 265, "2", "slices"),
            ("Cheddar Cheese", "Dairy & Eggs", 402, "75", "g"),
            ("Butter", "Dairy & Eggs", 717, "2", "tbsp"),
            ("Garlic", "Produce", 149, "2", "cloves"),
        ],
    },
    {
        "name": "Golden French Cheesy Omelette",
        "description": "Velvety French-style folded eggs loaded with melted aged cheddar, fragrant butter, and cracked pepper.",
        "cooking_time": 10,
        "instructions": "1. Whisk eggs with sea salt and cracked black pepper until smooth.\n2. Melt butter in a non-stick skillet on medium heat until foaming.\n3. Pour eggs, swirl gently in circular motions to form silky soft curds.\n4. Sprinkle cheddar down center, fold carefully, and slide onto a warm plate.",
        "ingredients": [
            ("Eggs", "Dairy & Eggs", 155, "3", "pcs"),
            ("Cheddar Cheese", "Dairy & Eggs", 402, "50", "g"),
            ("Butter", "Dairy & Eggs", 717, "1", "tbsp"),
            ("Black Pepper", "Pantry & Spices", 251, "1", "pinch"),
        ],
    },
    {
        "name": "Tuscan Garlic Herb Chicken Skillet",
        "description": "Pan-seared tender chicken breast simmered in rich garlic olive oil, rosemary, cracked pepper, and parmesan glaze.",
        "cooking_time": 25,
        "instructions": "1. Season chicken breasts with sea salt, black pepper, and dried Italian herbs.\n2. Heat olive oil and butter in a cast-iron skillet over medium-high.\n3. Sear chicken for 6-7 minutes per side until deeply golden.\n4. Add minced garlic cloves in final 2 minutes for an aromatic pan sauce. Rest 5 minutes before slicing.",
        "ingredients": [
            ("Chicken Breast", "Meat & Seafood", 165, "400", "g"),
            ("Garlic", "Produce", 149, "4", "cloves"),
            ("Olive Oil", "Pantry & Spices", 884, "2", "tbsp"),
            ("Butter", "Dairy & Eggs", 717, "1", "tbsp"),
            ("Parmesan", "Dairy & Eggs", 431, "30", "g"),
        ],
    },
    {
        "name": "Classic Italian Creamy Carbonara",
        "description": "Al dente pasta tossed in a luxurious emulsion of egg yolks, crisp cured bacon, parmesan, and cracked pepper.",
        "cooking_time": 20,
        "instructions": "1. Boil pasta in salted water until al dente; reserve 1/2 cup pasta cooking water.\n2. Whisk egg yolks with finely grated parmesan and cracked black pepper in a bowl.\n3. Cook bacon until crisp in a skillet.\n4. Toss hot pasta directly into skillet, remove from heat, and rapidly stir in egg-cheese mixture with a splash of pasta water until glossy and velvety.",
        "ingredients": [
            ("Pasta", "Grains & Pasta", 131, "250", "g"),
            ("Eggs", "Dairy & Eggs", 155, "3", "pcs"),
            ("Bacon", "Meat & Seafood", 541, "100", "g"),
            ("Parmesan", "Dairy & Eggs", 431, "60", "g"),
            ("Black Pepper", "Pantry & Spices", 251, "1", "tsp"),
            ("Olive Oil", "Pantry & Spices", 884, "1", "tbsp"),
        ],
    },
    {
        "name": "Rustic Pomodoro Penne Pasta",
        "description": "Rich slow-simmered tomato sauce with sweet basil, sautéed garlic, extra virgin olive oil, and aged parmesan.",
        "cooking_time": 18,
        "instructions": "1. Sauté crushed garlic in shimmering olive oil until fragrant.\n2. Pour in crushed tomato sauce, season with salt and pepper, and simmer for 12 minutes.\n3. Cook pasta al dente and fold directly into simmering sauce.\n4. Finish with freshly grated parmesan and fresh basil leaves.",
        "ingredients": [
            ("Pasta", "Grains & Pasta", 131, "300", "g"),
            ("Tomato Sauce", "Pantry & Spices", 29, "250", "ml"),
            ("Garlic", "Produce", 149, "3", "cloves"),
            ("Olive Oil", "Pantry & Spices", 884, "2", "tbsp"),
            ("Parmesan", "Dairy & Eggs", 431, "40", "g"),
        ],
    },
    {
        "name": "Mediterranean Sautéed Garlic Shrimp",
        "description": "Plump succulent shrimp sizzled in extra virgin olive oil, chili flakes, minced garlic, lemon, and butter.",
        "cooking_time": 12,
        "instructions": "1. Heat olive oil and butter in a large skillet over medium-high heat.\n2. Add garlic and red chili flakes, sizzling for 30 seconds until aromatic.\n3. Add shrimp in a single layer; cook 2 minutes per side until pink and opaque.\n4. Season with sea salt and squeeze fresh lemon juice. Serve with crusty bread.",
        "ingredients": [
            ("Shrimp", "Meat & Seafood", 99, "350", "g"),
            ("Garlic", "Produce", 149, "5", "cloves"),
            ("Olive Oil", "Pantry & Spices", 884, "3", "tbsp"),
            ("Butter", "Dairy & Eggs", 717, "1", "tbsp"),
            ("Salt", "Pantry & Spices", 0, "1", "tsp"),
            ("Bread", "Grains & Pasta", 265, "2", "slices"),
        ],
    },
    {
        "name": "Avocado & Poached Egg Sourdough Toast",
        "description": "Creamy whipped avocado on toasted sourdough topped with a delicate runny poached egg, chili flakes, and sea salt.",
        "cooking_time": 10,
        "instructions": "1. Toast sourdough slices until golden and sturdy.\n2. Mash ripe avocado with a pinch of sea salt and lemon juice.\n3. Poach fresh eggs in gently simmering water for 3 minutes.\n4. Spread mashed avocado generously over toast, crown with poached egg, and dust with black pepper.",
        "ingredients": [
            ("Bread", "Grains & Pasta", 265, "2", "slices"),
            ("Avocado", "Produce", 160, "1", "whole"),
            ("Eggs", "Dairy & Eggs", 155, "2", "pcs"),
            ("Olive Oil", "Pantry & Spices", 884, "1", "tsp"),
            ("Salt", "Pantry & Spices", 0, "1", "pinch"),
            ("Black Pepper", "Pantry & Spices", 251, "1", "pinch"),
        ],
    },
    {
        "name": "Savory Garlic Fried Rice with Egg",
        "description": "Fragrant wok-tossed jasmine rice infused with golden toasted garlic chips, scrambled egg ribbons, and soy butter.",
        "cooking_time": 15,
        "instructions": "1. Sizzle thinly sliced garlic in olive oil and butter until crispy golden chips; reserve half for garnish.\n2. Push garlic to side, scramble eggs into soft curds.\n3. Add cold cooked rice, toss over high heat with soy sauce, black pepper and a drizzle of butter.\n4. Top with crispy garlic chips and serve immediately.",
        "ingredients": [
            ("Rice", "Grains & Pasta", 130, "300", "g"),
            ("Eggs", "Dairy & Eggs", 155, "2", "pcs"),
            ("Garlic", "Produce", 149, "4", "cloves"),
            ("Butter", "Dairy & Eggs", 717, "1.5", "tbsp"),
            ("Olive Oil", "Pantry & Spices", 884, "1", "tbsp"),
            ("Soy Sauce", "Pantry & Spices", 53, "1", "tbsp"),
            ("Black Pepper", "Pantry & Spices", 251, "1", "tsp"),
        ],
    },
    {
        "name": "Gourmet Shakshuka with Feta & Crusty Bread",
        "description": "Poached eggs nestled in a spiced Mediterranean tomato pepper stew topped with creamy crumbled cheese and warm bread.",
        "cooking_time": 22,
        "instructions": "1. Heat olive oil in a skillet, sauté garlic, onions and bell peppers until soft.\n2. Pour in rich tomato sauce, season with salt and pepper, and simmer until thick.\n3. Make small wells in the sauce and crack eggs directly in.\n4. Cover and cook gently for 6 minutes until egg whites set but yolks remain runny. Crumble feta on top and serve with warm crusty bread.",
        "ingredients": [
            ("Eggs", "Dairy & Eggs", 155, "3", "pcs"),
            ("Tomato Sauce", "Pantry & Spices", 29, "300", "ml"),
            ("Bell Pepper", "Produce", 31, "1", "whole"),
            ("Garlic", "Produce", 149, "3", "cloves"),
            ("Olive Oil", "Pantry & Spices", 884, "2", "tbsp"),
            ("Feta Cheese", "Dairy & Eggs", 264, "50", "g"),
            ("Bread", "Grains & Pasta", 265, "3", "slices"),
        ],
    },
    {
        "name": "Fluffy Buttermilk Breakfast Pancakes",
        "description": "Golden light-as-air pancakes served with melting butter and pure maple syrup drizzle.",
        "cooking_time": 15,
        "instructions": "1. Whisk eggs, milk, and melted butter in a bowl.\n2. Gently fold flour and sugar until combined without overmixing.\n3. Ladle batter onto a hot buttered griddle over medium heat.\n4. Flip when bubbles form on top (2-3 min) and cook until golden brown. Drizzle with maple syrup.",
        "ingredients": [
            ("Flour", "Grains & Pasta", 364, "200", "g"),
            ("Milk", "Dairy & Eggs", 42, "250", "ml"),
            ("Eggs", "Dairy & Eggs", 155, "2", "pcs"),
            ("Butter", "Dairy & Eggs", 717, "3", "tbsp"),
            ("Sugar", "Pantry & Spices", 387, "2", "tbsp"),
            ("Maple Syrup", "Pantry & Spices", 260, "3", "tbsp"),
        ],
    },
    {
        "name": "Classic Affogato al Caffe",
        "description": "Silky scoop of rich vanilla ice cream drowned in a hot shot of dark espresso with shaved dark chocolate.",
        "cooking_time": 5,
        "instructions": "1. Place a large scoop of artisanal vanilla ice cream into a chilled glass or ceramic cup.\n2. Brew a piping hot fresh double espresso shot.\n3. Pour hot espresso immediately over the cold ice cream.\n4. Garnish with a sprinkle of cocoa powder and enjoy immediately.",
        "ingredients": [
            ("Vanilla Ice Cream", "Dairy & Eggs", 207, "2", "scoops"),
            ("Cocoa Powder", "Pantry & Spices", 228, "1", "tsp"),
        ],
    },
    {
        "name": "Warm Banana Rum Crepes a la Mode",
        "description": "Delicate golden crepes folded over caramelized sweet bananas crowned with melting vanilla ice cream and honey.",
        "cooking_time": 15,
        "instructions": "1. Whisk flour, milk, eggs, and a pinch of salt into a silky thin batter.\n2. Cook crepes in a buttered non-stick pan for 1-2 minutes per side until golden.\n3. Sauté sliced bananas in butter and honey until golden and caramelized.\n4. Fold crepes with warm bananas and top with a scoop of vanilla ice cream.",
        "ingredients": [
            ("Flour", "Grains & Pasta", 364, "120", "g"),
            ("Milk", "Dairy & Eggs", 42, "200", "ml"),
            ("Eggs", "Dairy & Eggs", 155, "2", "pcs"),
            ("Banana", "Produce", 89, "2", "whole"),
            ("Butter", "Dairy & Eggs", 717, "2", "tbsp"),
            ("Honey", "Pantry & Spices", 304, "2", "tbsp"),
            ("Vanilla Ice Cream", "Dairy & Eggs", 207, "2", "scoops"),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the database with rich gourmet recipes and comprehensive ingredients catalog"

    def handle(self, *args, **options):
        self.stdout.write("Seeding ingredients catalog...")

        # 1. Seed complete ingredients catalog
        for ing_name, ing_cat, ing_cal in FULL_INGREDIENT_CATALOG:
            ing_obj, _ = Ingredient.objects.get_or_create(
                name=ing_name,
                defaults={
                    "category": ing_cat,
                    "calories_per_100g": ing_cal,
                }
            )
            ing_obj.category = ing_cat
            ing_obj.calories_per_100g = ing_cal
            ing_obj.save()

        self.stdout.write(f"Catalog has {Ingredient.objects.count()} ingredients.")

        # 2. Seed Recipes
        created_recipes = 0
        for r_data in RECIPE_CATALOG:
            recipe, created = Recipe.objects.get_or_create(
                name=r_data["name"],
                defaults={
                    "description": r_data["description"],
                    "cooking_time": r_data["cooking_time"],
                    "instructions": r_data["instructions"],
                }
            )
            recipe.description = r_data["description"]
            recipe.cooking_time = r_data["cooking_time"]
            recipe.instructions = r_data["instructions"]
            recipe.save()

            for ing_name, ing_cat, ing_cal, qty, unit in r_data["ingredients"]:
                ing_obj, _ = Ingredient.objects.get_or_create(
                    name=ing_name,
                    defaults={
                        "category": ing_cat,
                        "calories_per_100g": ing_cal,
                    }
                )
                RecipeIngredient.objects.get_or_create(
                    recipe=recipe,
                    ingredient=ing_obj,
                    defaults={
                        "quantity": qty,
                        "unit": unit,
                    }
                )
            created_recipes += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded {created_recipes} gourmet recipes and {Ingredient.objects.count()} rich ingredients!"
        ))
