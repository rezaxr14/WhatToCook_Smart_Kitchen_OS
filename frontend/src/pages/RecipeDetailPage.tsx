import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Clock, ChefHat, Check, ShoppingBag, Flame, Sparkles, Plus, ShoppingCart } from 'lucide-react';
import { Recipe } from '../types/recipe';
import { recipeApi } from '../api/recipeApi';
import { usePantry } from '../context/PantryContext';
import { useShoppingList } from '../context/ShoppingListContext';
import { CookingTimer } from '../components/recipe/CookingTimer';
import { ServingScaler, scaleQuantity } from '../components/recipe/ServingScaler';
import { SubstitutionModal } from '../components/recipe/SubstitutionModal';
import { StyledButton } from '../components/common/StyledButton';
import { RecipeChatBox } from '../components/recipe/RecipeChatBox';

export const RecipeDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [checkedIngredients, setCheckedIngredients] = useState<number[]>([]);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [servings, setServings] = useState<number>(4);
  const [substitutionModalOpen, setSubstitutionModalOpen] = useState(false);
  const [selectedSubIngredient, setSelectedSubIngredient] = useState('');

  const { isInPantry } = usePantry();
  const { addMultipleItems } = useShoppingList();

  useEffect(() => {
    const fetchRecipe = async () => {
      if (!id) return;
      setIsLoading(true);
      try {
        const data = await recipeApi.getRecipeById(Number(id));
        setRecipe(data);
      } catch (err) {
        console.error('Error loading recipe:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRecipe();
  }, [id]);

  const toggleIngredientCheck = (ingId: number) => {
    setCheckedIngredients((prev) =>
      prev.includes(ingId) ? prev.filter((i) => i !== ingId) : [...prev, ingId]
    );
  };

  const toggleStepCheck = (stepIdx: number) => {
    setCompletedSteps((prev) =>
      prev.includes(stepIdx) ? prev.filter((s) => s !== stepIdx) : [...prev, stepIdx]
    );
  };

  const handleAddAllToShoppingList = () => {
    if (!recipe) return;
    const itemsToAdd: Array<{ name: string; category?: string; quantity?: string; addedFrom?: string }> = [];

    if (recipe.recipe_ingredients && recipe.recipe_ingredients.length > 0) {
      recipe.recipe_ingredients.forEach((ri) => {
        if (!isInPantry(ri.ingredient.id)) {
          const scaledQty = scaleQuantity(ri.quantity, servings / 4);
          itemsToAdd.push({
            name: ri.ingredient.name,
            category: ri.ingredient.category || 'Produce',
            quantity: `${scaledQty} ${ri.unit}`.trim(),
            addedFrom: recipe.name,
          });
        }
      });
    } else if (recipe.ingredients) {
      recipe.ingredients.forEach((ing) => {
        if (!isInPantry(ing.id)) {
          itemsToAdd.push({
            name: ing.name,
            category: ing.category || 'Produce',
            addedFrom: recipe.name,
          });
        }
      });
    }

    if (itemsToAdd.length > 0) {
      addMultipleItems(itemsToAdd, true);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-6 animate-pulse">
        <div className="h-8 w-40 bg-stone-200 rounded-xl" />
        <div className="h-96 w-full bg-stone-200 rounded-3xl" />
      </div>
    );
  }

  if (!recipe) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <h2 className="text-2xl font-bold text-stone-900 mb-2">Recipe not found</h2>
        <Link to="/">
          <StyledButton $variant="primary">Back to Discover</StyledButton>
        </Link>
      </div>
    );
  }

  const instructionsList = recipe.instructions
    ? recipe.instructions.split('\n').filter((s) => s.trim().length > 0)
    : [];

  const getImageUrl = () => {
    if (recipe.image_url) return recipe.image_url;
    if (recipe.image) {
      if (recipe.image.startsWith('http') || recipe.image.startsWith('/')) return recipe.image;
      return `/media/${recipe.image}`;
    }
    return '/media/recipes/default.png';
  };

  const scaleMultiplier = servings / 4;

  return (
    <div className="max-w-5xl mx-auto space-y-10 pb-20">
      {/* Back Link */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-stone-600 hover:text-stone-900 font-semibold text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Recipes</span>
      </Link>

      {/* Hero Header Card */}
      <div className="relative rounded-3xl overflow-hidden shadow-2xl bg-stone-900 text-white min-h-[380px] flex flex-col justify-end p-8 sm:p-12">
        <img
          src={getImageUrl()}
          alt={recipe.name}
          className="absolute inset-0 w-full h-full object-cover opacity-60"
          onError={(e) => {
            // fall back to the recipe's own card photo when the hero fails
            const t = e.target as HTMLImageElement;
            const alt = `/media/${recipe.image ?? ''}`;
            if (t.src !== alt && (recipe.image ?? '').length > 0) t.src = alt;
            else if (t.src !== '/media/recipes/default.png') t.src = '/media/recipes/default.png';
          }}
        />
        <div className="absolute inset-0 bg-linear-to-t/srgb from-stone-950 via-stone-950/60 to-transparent" />

        <div className="relative z-10 space-y-4 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            {recipe.cooking_time && (
              <span className="bg-amber-500/90 text-stone-950 text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5 shadow-xs">
                <Clock className="w-3.5 h-3.5" />
                <span>{recipe.cooking_time} mins Total Cook Time</span>
              </span>
            )}
            <span className="bg-white/20 backdrop-blur-md text-white text-xs font-semibold px-3 py-1 rounded-full">
              {recipe.ingredients?.length || 0} Ingredients
            </span>
          </div>

          <h1 className="text-3xl sm:text-5xl font-extrabold tracking-tight drop-shadow-md">
            {recipe.name}
          </h1>

          <p className="text-stone-300 text-sm sm:text-base leading-relaxed max-w-2xl">
            {recipe.description}
          </p>
        </div>
      </div>

      {/* Main Grid: Ingredients vs Instructions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Ingredients Checklist */}
        <div className="space-y-6">
          <div className="bg-white rounded-3xl p-6 border border-stone-200 shadow-xs space-y-4 sticky top-24">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-stone-900 text-lg flex items-center gap-2">
                <ShoppingBag className="w-5 h-5 text-brand-500" />
                <span>Ingredients</span>
              </h3>
              <span className="text-xs text-stone-500 font-semibold">
                {checkedIngredients.length} / {recipe.ingredients?.length || 0} prepped
              </span>
            </div>

            {/* Serving Scaler */}
            <ServingScaler
              currentServings={servings}
              baseServings={4}
              onChange={(s) => setServings(s)}
            />

            <div className="flex items-center justify-between pt-1">
              <p className="text-xs text-stone-500">
                Click items to mark prepped:
              </p>
              <button
                onClick={handleAddAllToShoppingList}
                className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center gap-1 hover:underline"
              >
                <ShoppingCart className="w-3.5 h-3.5" />
                <span>Add Missing</span>
              </button>
            </div>

            <div className="space-y-2">
              {recipe.recipe_ingredients && recipe.recipe_ingredients.length > 0 ? (
                recipe.recipe_ingredients.map((ri) => {
                  const isChecked = checkedIngredients.includes(ri.ingredient.id);
                  const isStocked = isInPantry(ri.ingredient.id);
                  const scaledQuantity = scaleQuantity(ri.quantity, scaleMultiplier);

                  return (
                    <div
                      key={ri.id}
                      className={`w-full flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
 isChecked
 ? 'bg-emerald-50 border-emerald-200 text-emerald-950 opacity-70'
 : 'bg-stone-50/80 border-stone-200 hover:border-brand-300 text-stone-800'
 }`}
                    >
                      <button
                        onClick={() => toggleIngredientCheck(ri.ingredient.id)}
                        className="flex items-center gap-2.5 min-w-0 flex-1 text-left"
                      >
                        <div
                          className={`w-5 h-5 rounded-lg flex items-center justify-center border ${
 isChecked
 ? 'bg-emerald-600 border-emerald-600 text-white'
 : 'bg-white border-stone-300'
 }`}
                        >
                          {isChecked && <Check className="w-3.5 h-3.5" />}
                        </div>
                        <span
                          className={`text-sm font-semibold truncate capitalize ${
 isChecked ? 'line-through' : ''
 }`}
                        >
                          {ri.ingredient.name}
                        </span>
                      </button>

                      <div className="flex items-center gap-2 text-xs text-stone-500 shrink-0">
                        <span className="font-mono font-bold text-stone-700">
                          {scaledQuantity} {ri.unit}
                        </span>
                        {isStocked ? (
                          <span className="text-[10px] px-1.5 py-0.2 rounded-sm bg-emerald-100 text-emerald-800 font-sans font-bold">
                            In Pantry
                          </span>
                        ) : (
                          <button
                            onClick={() => {
                              setSelectedSubIngredient(ri.ingredient.name);
                              setSubstitutionModalOpen(true);
                            }}
                            title="Find Substitute"
                            className="p-1 rounded-lg text-amber-600 hover:bg-amber-100 transition-colors"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })
              ) : (
                recipe.ingredients?.map((ing) => {
                  const isChecked = checkedIngredients.includes(ing.id);
                  const isStocked = isInPantry(ing.id);
                  return (
                    <div
                      key={ing.id}
                      className={`w-full flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
 isChecked
 ? 'bg-emerald-50 border-emerald-200 text-emerald-950 opacity-70'
 : 'bg-stone-50/80 border-stone-200 hover:border-brand-300 text-stone-800'
 }`}
                    >
                      <button
                        onClick={() => toggleIngredientCheck(ing.id)}
                        className="flex items-center gap-2.5 min-w-0 flex-1 text-left"
                      >
                        <div
                          className={`w-5 h-5 rounded-lg flex items-center justify-center border ${
 isChecked
 ? 'bg-emerald-600 border-emerald-600 text-white'
 : 'bg-white border-stone-300'
 }`}
                        >
                          {isChecked && <Check className="w-3.5 h-3.5" />}
                        </div>
                        <span
                          className={`text-sm font-semibold truncate capitalize ${
 isChecked ? 'line-through' : ''
 }`}
                        >
                          {ing.name}
                        </span>
                      </button>

                      {!isStocked && (
                        <button
                          onClick={() => {
                            setSelectedSubIngredient(ing.name);
                            setSubstitutionModalOpen(true);
                          }}
                          title="Find Substitute"
                          className="p-1 rounded-lg text-amber-600 hover:bg-amber-100 transition-colors"
                        >
                          <Sparkles className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* Step Timer Widget */}
            <div className="pt-4 border-t border-stone-100">
              <CookingTimer
                initialMinutes={recipe.cooking_time || 15}
                label={`${recipe.name} Cooking Timer`}
              />
            </div>
          </div>
        </div>

        {/* Step-by-Step Instructions */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-stone-200 shadow-xs space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-extrabold text-stone-900 flex items-center gap-2">
                <ChefHat className="w-6 h-6 text-brand-500" />
                <span>Step-by-Step Method</span>
              </h2>
              <span className="text-xs font-semibold text-stone-500">
                {instructionsList.length} Steps
              </span>
            </div>

            <div className="space-y-4">
              {instructionsList.map((step, idx) => {
                const isDone = completedSteps.includes(idx);
                return (
                  <div
                    key={idx}
                    onClick={() => toggleStepCheck(idx)}
                    className={`p-5 rounded-2xl border transition-all cursor-pointer flex items-start gap-4 ${
 isDone
 ? 'bg-emerald-50/60 border-emerald-200 opacity-75'
 : 'bg-stone-50/60 border-stone-200 hover:border-brand-300 hover:bg-white'
 }`}
                  >
                    <div
                      className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
 isDone
 ? 'bg-emerald-600 text-white'
 : 'bg-brand-500 text-white shadow-xs shadow-brand-500/20'
 }`}
                    >
                      {isDone ? <Check className="w-4 h-4" /> : idx + 1}
                    </div>

                    <div className="flex-1">
                      <p className={`text-stone-800 text-sm leading-relaxed ${isDone ? 'line-through text-stone-500' : ''}`}>
                        {step}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Interactive AI Sous-Chef Chat Box */}
      <RecipeChatBox
        recipeName={recipe.name}
        ingredients={recipe.ingredients?.map((i) => i.name)}
        instructions={instructionsList}
      />

      {/* Substitution Finder Modal */}
      <SubstitutionModal
        isOpen={substitutionModalOpen}
        onClose={() => setSubstitutionModalOpen(false)}
        initialIngredient={selectedSubIngredient}
      />
    </div>
  );
};
