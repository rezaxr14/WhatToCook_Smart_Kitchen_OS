import React, { useState, useEffect } from 'react';
import { Link } from 'react-router';
import { ChefHat, ShoppingBag, CheckCircle, AlertCircle, Sparkles, ArrowRight, ShoppingCart } from 'lucide-react';
import { CanCookResponse } from '../types/recipe';
import { recipeApi } from '../api/recipeApi';
import { usePantry } from '../context/PantryContext';
import { useShoppingList } from '../context/ShoppingListContext';
import { RecipeCard } from '../components/recipe/RecipeCard';
import { StyledButton } from '../components/common/StyledButton';
import { StyledCard } from '../components/common/StyledCard';

export const CanCookPage: React.FC = () => {
  const [data, setData] = useState<CanCookResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'full' | 'partial'>('full');

  const { pantryIngredients } = usePantry();
  const { addMultipleItems } = useShoppingList();

  useEffect(() => {
    const fetchCanCook = async () => {
      setIsLoading(true);
      try {
        const res = await recipeApi.getCanCookRecipes();
        setData(res);
        if (res.full_matches.length === 0 && res.partial_matches.length > 0) {
          setActiveTab('partial');
        }
      } catch (err) {
        console.error('Error fetching can cook recipes:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchCanCook();
  }, [pantryIngredients]);

  const handleAddAllMissingToGrocery = () => {
    if (!data?.partial_matches) return;
    const itemsToAdd: Array<{ name: string; category?: string; addedFrom?: string }> = [];

    data.partial_matches.forEach((r) => {
      if (r.missing_ingredients) {
        r.missing_ingredients.forEach((ingName) => {
          if (!itemsToAdd.some((item) => item.name.toLowerCase() === ingName.toLowerCase())) {
            itemsToAdd.push({
              name: ingName,
              category: 'Produce',
              addedFrom: r.name,
            });
          }
        });
      }
    });

    if (itemsToAdd.length > 0) {
      addMultipleItems(itemsToAdd, true);
    }
  };

  const fullCount = data?.total_full_matches || 0;
  const partialCount = data?.total_partial_matches || 0;

  return (
    <div className="space-y-8 pb-16">
      {/* Header Banner */}
      <div className="bg-linear-to-br/srgb from-brand-600 via-orange-600 to-amber-600 rounded-3xl p-6 sm:p-10 text-white shadow-xl relative overflow-hidden">
        <div className="relative z-10 max-w-2xl space-y-3">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-white/20 backdrop-blur-md">
            <ChefHat className="w-3.5 h-3.5" />
            <span>Smart Kitchen Matching</span>
          </div>

          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight">
            What You Can Cook Right Now
          </h1>

          <p className="text-white/90 text-sm sm:text-base leading-relaxed">
            Based on the <strong className="text-amber-200">{pantryIngredients.length} ingredients</strong> in your pantry, here are the recipes you can prepare with zero food waste.
          </p>

          <div className="pt-2 flex items-center gap-3">
            <Link to="/pantry">
              <StyledButton $variant="secondary" $size="sm">
                <ShoppingBag className="w-4 h-4 text-stone-700" />
                <span>Adjust Pantry ({pantryIngredients.length})</span>
              </StyledButton>
            </Link>
            <Link to="/ai-chef">
              <StyledButton $variant="outline" $size="sm" className="border-white/30 text-white hover:bg-white/10">
                <Sparkles className="w-4 h-4 text-amber-300" />
                <span>Ask AI Chef for Custom Ideas</span>
              </StyledButton>
            </Link>
          </div>
        </div>
      </div>

      {/* Matching Tabs & Quick Actions */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-200 pb-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setActiveTab('full')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold transition-all ${
 activeTab === 'full'
 ? 'bg-emerald-600 text-white shadow-md shadow-emerald-600/20'
 : 'bg-white text-stone-600 hover:bg-stone-100 border border-stone-200'
 }`}
          >
            <CheckCircle className="w-4 h-4" />
            <span>100% Ready to Cook</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-bold ${
 activeTab === 'full' ? 'bg-white/20 text-white' : 'bg-stone-200 text-stone-700'
 }`}
            >
              {fullCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('partial')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-2xl text-sm font-bold transition-all ${
 activeTab === 'partial'
 ? 'bg-amber-600 text-white shadow-md shadow-amber-600/20'
 : 'bg-white text-stone-600 hover:bg-stone-100 border border-stone-200'
 }`}
          >
            <AlertCircle className="w-4 h-4" />
            <span>Missing 1 or 2 Items</span>
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-bold ${
 activeTab === 'partial' ? 'bg-white/20 text-white' : 'bg-stone-200 text-stone-700'
 }`}
            >
              {partialCount}
            </span>
          </button>
        </div>

        {activeTab === 'partial' && partialCount > 0 && (
          <button
            onClick={handleAddAllMissingToGrocery}
            className="flex items-center gap-1.5 px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white font-bold text-xs rounded-xl transition-all"
          >
            <ShoppingCart className="w-4 h-4" />
            <span>Add All Missing to Grocery List</span>
          </button>
        )}
      </div>

      {/* Recipe Grid Output */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className="rounded-3xl border border-stone-200 bg-white p-4 h-96 animate-pulse"
            >
              <div className="w-full h-48 bg-stone-200 rounded-2xl mb-4" />
              <div className="space-y-2">
                <div className="w-2/3 h-5 bg-stone-200 rounded-lg" />
                <div className="w-full h-3 bg-stone-100 rounded-lg" />
              </div>
            </div>
          ))}
        </div>
      ) : activeTab === 'full' ? (
        fullCount > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {data?.full_matches.map((recipe) => (
              <RecipeCard key={recipe.id} recipe={recipe} isMatched />
            ))}
          </div>
        ) : (
          <StyledCard className="p-12 text-center max-w-lg mx-auto bg-white">
            <div className="w-16 h-16 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mx-auto mb-4">
              <ShoppingBag className="w-8 h-8" />
            </div>
            <h3 className="text-xl font-bold text-stone-900 mb-2">No 100% matched recipes yet</h3>
            <p className="text-stone-500 text-sm mb-6 leading-relaxed">
              Add a few more ingredients to your pantry or check out the dishes where you're only missing 1 or 2 items!
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <StyledButton $variant="primary" onClick={() => setActiveTab('partial')}>
                <AlertCircle className="w-4 h-4" />
                <span>View Partial Matches ({partialCount})</span>
              </StyledButton>
              <Link to="/pantry">
                <StyledButton $variant="secondary">
                  <span>Add More Ingredients</span>
                </StyledButton>
              </Link>
            </div>
          </StyledCard>
        )
      ) : partialCount > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {data?.partial_matches.map((recipe) => (
            <RecipeCard key={recipe.id} recipe={recipe} isMatched />
          ))}
        </div>
      ) : (
        <StyledCard className="p-12 text-center max-w-lg mx-auto bg-white">
          <h3 className="text-xl font-bold text-stone-900 mb-2">No partial recipes found</h3>
          <p className="text-stone-500 text-sm mb-6">
            Stock up your pantry shelf to unlock instant recipe recommendations.
          </p>
          <Link to="/pantry">
            <StyledButton $variant="primary">Go to Pantry</StyledButton>
          </Link>
        </StyledCard>
      )}
    </div>
  );
};
