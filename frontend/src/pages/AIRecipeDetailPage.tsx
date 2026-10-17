import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link } from 'react-router-dom';
import { ArrowLeft, Sparkles, ChefHat, Clock, Check, Flame, Award, Lightbulb, ShoppingCart } from 'lucide-react';
import { AIRecipeDetail, AIRecipeInstruction } from '../types/ai';
import { aiApi } from '../api/aiApi';
import { useShoppingList } from '../context/ShoppingListContext';
import { usePantry } from '../context/PantryContext';
import { CookingTimer } from '../components/recipe/CookingTimer';
import { ServingScaler, scaleQuantity } from '../components/recipe/ServingScaler';
import { SubstitutionModal } from '../components/recipe/SubstitutionModal';
import { LoadingChef } from '../components/common/LoadingChef';
import { StyledButton } from '../components/common/StyledButton';
import { RecipeChatBox } from '../components/recipe/RecipeChatBox';
import { getDishImageUrl } from '../utils/imageUtils';

export const AIRecipeDetailPage: React.FC = () => {
  const { name } = useParams<{ name: string }>();
  const [searchParams] = useSearchParams();
  const provider = (searchParams.get('provider') as any) || 'gemini';

  const [recipe, setRecipe] = useState<AIRecipeDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [completedSteps, setCompletedSteps] = useState<number[]>([]);
  const [checkedIngredients, setCheckedIngredients] = useState<string[]>([]);
  const [servings, setServings] = useState<number>(4);
  const [substitutionModalOpen, setSubstitutionModalOpen] = useState(false);
  const [selectedSubIngredient, setSelectedSubIngredient] = useState('');

  const { addMultipleItems } = useShoppingList();
  const { isInPantry, activeModel, handleRateLimitedModels } = usePantry();

  useEffect(() => {
    const fetchDetail = async () => {
      if (!name) return;
      setIsLoading(true);
      try {
        const data = await aiApi.getRecipeDetail(name, provider, activeModel);
        setRecipe(data);
        if (data.rate_limited_models && data.rate_limited_models.length > 0) {
          handleRateLimitedModels(data.rate_limited_models);
        }
      } catch (err) {
        console.error('Error fetching AI recipe detail:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchDetail();
  }, [name, provider, activeModel, handleRateLimitedModels]);

  const toggleStep = (idx: number) => {
    setCompletedSteps((prev) =>
      prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]
    );
  };

  const toggleIngredient = (ingName: string) => {
    setCheckedIngredients((prev) =>
      prev.includes(ingName) ? prev.filter((i) => i !== ingName) : [...prev, ingName]
    );
  };

  const handleAddAllToShoppingList = () => {
    if (!recipe || !recipe.ingredients) return;
    const items = recipe.ingredients.map((ing) => {
      const scaledAmount = scaleQuantity(String(ing.amount), servings / 4);
      return {
        name: ing.name,
        category: 'Produce',
        quantity: `${scaledAmount} ${ing.unit}`.trim(),
        addedFrom: recipe.name,
      };
    });
    addMultipleItems(items, true);
  };

  if (isLoading) {
    return (
      <div className="py-12">
        <LoadingChef message={`Master Chef is writing the complete recipe for ${name}...`} provider={provider} />
      </div>
    );
  }

  if (!recipe) {
    return (
      <div className="max-w-md mx-auto py-16 text-center">
        <h2 className="text-2xl font-bold text-stone-900 mb-2">Recipe detail could not be generated</h2>
        <Link to="/ai-chef">
          <StyledButton $variant="primary">Back to AI Studio</StyledButton>
        </Link>
      </div>
    );
  }

  const scaleMultiplier = servings / 4;

  return (
    <div className="max-w-5xl mx-auto space-y-10 pb-20">
      {/* Back Link */}
      <Link
        to="/ai-chef"
        className="inline-flex items-center gap-2 text-stone-600 hover:text-stone-900 font-semibold text-sm transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to AI Chef Studio</span>
      </Link>

      {/* Hero Card */}
      <div className="relative rounded-3xl overflow-hidden shadow-2xl bg-stone-900 text-white min-h-[380px] flex flex-col justify-end p-8 sm:p-12">
        <img
          src={getDishImageUrl(recipe.name, recipe.image)}
          alt={recipe.name}
          className="absolute inset-0 w-full h-full object-cover opacity-60"
          onError={(e) => {
            (e.target as HTMLImageElement).src = getDishImageUrl(recipe.name);
          }}
        />
        <div className="absolute inset-0 bg-linear-to-t/srgb from-stone-950 via-stone-950/60 to-transparent" />

        <div className="relative z-10 space-y-4 max-w-3xl">
          <div className="flex flex-wrap items-center gap-2">
            <span className="bg-amber-500/90 text-stone-950 text-xs font-bold px-3 py-1 rounded-full flex items-center gap-1.5 shadow-xs">
              <Sparkles className="w-3.5 h-3.5" />
              <span>AI Master Chef Recipe</span>
            </span>
            <span className="bg-white/20 backdrop-blur-md text-white text-xs font-semibold px-3 py-1 rounded-full flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              <span>{recipe.time_minutes || 25} mins</span>
            </span>
            <span className="bg-emerald-500/90 text-white text-xs font-semibold px-3 py-1 rounded-full">
              {recipe.difficulty || 'Easy'}
            </span>
            <span className="bg-blue-500/90 text-white text-xs font-semibold px-3 py-1 rounded-full">
              {recipe.cuisine || 'Gourmet'}
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

      {/* Nutrition Macro Bar */}
      {recipe.nutrition && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-xs text-center">
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Calories</div>
            <div className="text-xl font-extrabold text-stone-900 mt-1">{recipe.nutrition.calories || '350 kcal'}</div>
          </div>
          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-xs text-center">
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Protein</div>
            <div className="text-xl font-extrabold text-emerald-600 mt-1">{recipe.nutrition.protein || '24g'}</div>
          </div>
          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-xs text-center">
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Carbs</div>
            <div className="text-xl font-extrabold text-amber-600 mt-1">{recipe.nutrition.carbs || '38g'}</div>
          </div>
          <div className="bg-white rounded-2xl p-4 border border-stone-200 shadow-xs text-center">
            <div className="text-xs font-semibold text-stone-500 uppercase tracking-wider">Fats</div>
            <div className="text-xl font-extrabold text-orange-600 mt-1">{recipe.nutrition.fat || '12g'}</div>
          </div>
        </div>
      )}

      {/* Main Grid: Ingredients + Steps */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Ingredients Checklist */}
        <div className="space-y-6">
          <div className="bg-white rounded-3xl p-6 border border-stone-200 shadow-xs space-y-4 sticky top-24">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-stone-900 text-lg flex items-center gap-2">
                <ChefHat className="w-5 h-5 text-brand-500" />
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
                Mark items as ready:
              </p>
              <button
                onClick={handleAddAllToShoppingList}
                className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center gap-1 hover:underline"
              >
                <ShoppingCart className="w-3.5 h-3.5" />
                <span>Add to List</span>
              </button>
            </div>

            <div className="space-y-2">
              {recipe.ingredients?.map((ing, idx) => {
                const isChecked = checkedIngredients.includes(ing.name);
                const scaledAmount = scaleQuantity(String(ing.amount), scaleMultiplier);

                return (
                  <div
                    key={idx}
                    className={`w-full flex items-center justify-between p-3 rounded-2xl border text-left transition-all ${
 isChecked
 ? 'bg-emerald-50 border-emerald-200 text-emerald-950 opacity-70'
 : 'bg-stone-50/80 border-stone-200 hover:border-brand-300 text-stone-800'
 }`}
                  >
                    <button
                      onClick={() => toggleIngredient(ing.name)}
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
                      <span className={`text-sm font-semibold truncate ${isChecked ? 'line-through' : ''}`}>
                        {ing.name}
                      </span>
                    </button>

                    <div className="flex items-center gap-2 text-xs text-stone-500 shrink-0">
                      <span className="font-mono font-bold text-stone-700">
                        {scaledAmount} {ing.unit}
                      </span>
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
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Step Timer */}
            <div className="pt-4 border-t border-stone-100">
              <CookingTimer initialMinutes={recipe.time_minutes || 20} label="AI Chef Timer" />
            </div>
          </div>
        </div>

        {/* Step-by-Step Culinary Method */}
        <div className="lg:col-span-2 space-y-6">
          <div className="bg-white rounded-3xl p-6 sm:p-8 border border-stone-200 shadow-xs space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-extrabold text-stone-900 flex items-center gap-2">
                <Sparkles className="w-6 h-6 text-brand-500" />
                <span>Chef Cooking Method</span>
              </h2>
              <span className="text-xs font-semibold text-stone-500">
                {recipe.instructions?.length || 0} Steps
              </span>
            </div>

            <div className="space-y-4">
              {recipe.instructions?.map((inst, idx) => {
                const isDone = completedSteps.includes(idx);
                const stepText = typeof inst === 'string' ? inst : inst.step;
                const chefTip = typeof inst === 'object' && inst.chef_tip ? inst.chef_tip : null;
                const timeMin = typeof inst === 'object' && inst.time_minutes ? inst.time_minutes : null;

                return (
                  <div
                    key={idx}
                    onClick={() => toggleStep(idx)}
                    className={`p-5 rounded-2xl border transition-all cursor-pointer space-y-3 ${
 isDone
 ? 'bg-emerald-50/60 border-emerald-200 opacity-75'
 : 'bg-stone-50/60 border-stone-200 hover:border-brand-300 hover:bg-white'
 }`}
                  >
                    <div className="flex items-start gap-4">
                      <div
                        className={`w-8 h-8 rounded-xl flex items-center justify-center font-bold text-sm shrink-0 ${
 isDone
 ? 'bg-emerald-600 text-white'
 : 'bg-linear-to-tr/srgb from-brand-500 to-amber-500 text-white shadow-xs'
 }`}
                      >
                        {isDone ? <Check className="w-4 h-4" /> : idx + 1}
                      </div>

                      <div className="flex-1">
                        <p className={`text-stone-800 text-sm leading-relaxed ${isDone ? 'line-through text-stone-500' : ''}`}>
                          {stepText}
                        </p>

                        {timeMin && (
                          <div className="flex items-center gap-1 text-xs text-stone-500 font-semibold mt-2">
                            <Clock className="w-3.5 h-3.5 text-brand-500" />
                            <span>Approx. {timeMin} minutes</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Master Chef Secret Tip */}
                    {chefTip && (
                      <div className="ml-12 p-3 rounded-xl bg-amber-50/90 border border-amber-200/80 text-xs text-amber-900 flex items-start gap-2">
                        <Lightbulb className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                        <div>
                          <strong className="font-bold">Chef's Secret: </strong>
                          <span>{chefTip}</span>
                        </div>
                      </div>
                    )}
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
        ingredients={recipe.ingredients}
        instructions={recipe.instructions}
      />

      {/* Substitution Modal */}
      <SubstitutionModal
        isOpen={substitutionModalOpen}
        onClose={() => setSubstitutionModalOpen(false)}
        initialIngredient={selectedSubIngredient}
      />
    </div>
  );
};
