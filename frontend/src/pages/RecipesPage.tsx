import React, { useState, useEffect, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Sparkles,
  ChefHat,
  ShoppingBag,
  Camera,
  Clock,
} from 'lucide-react';
import { Recipe } from '../types/recipe';
import { recipeApi } from '../api/recipeApi';
import { useAuth } from '../context/AuthContext';
import { usePantry } from '../context/PantryContext';
import { useShoppingList } from '../context/ShoppingListContext';
import { RecipeGrid } from '../components/recipe/RecipeGrid';
import { RecipeFilter } from '../components/recipe/RecipeFilter';
import { StyledButton } from '../components/common/StyledButton';

export const RecipesPage: React.FC = () => {
  const { user, isAuthenticated } = useAuth();
  const { t } = useTranslation();
  const { pantryIngredients } = usePantry();
  const { items: shoppingItems } = useShoppingList();

  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');
  const [maxCookTime, setMaxCookTime] = useState(90);

  useEffect(() => {
    const fetchRecipes = async () => {
      setIsLoading(true);
      try {
        const data = await recipeApi.getAllRecipes();
        setRecipes(data);
      } catch (err) {
        console.error('Error fetching recipes:', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchRecipes();
  }, []);

  // Filter recipes
  const filteredRecipes = useMemo(() => {
    return recipes.filter((recipe) => {
      const term = searchTerm.toLowerCase();
      const matchesName = recipe.name.toLowerCase().includes(term);
      const matchesDesc = recipe.description?.toLowerCase().includes(term);
      const matchesIng = recipe.ingredients?.some((i) => i.name.toLowerCase().includes(term));
      const matchesSearch = !searchTerm || matchesName || matchesDesc || matchesIng;

      const matchesTime = maxCookTime >= 90 || (recipe.cooking_time ? recipe.cooking_time <= maxCookTime : true);

      let matchesCat = true;
      if (selectedCategory === 'Quick (< 20m)') {
        matchesCat = (recipe.cooking_time || 0) <= 20;
      } else if (selectedCategory === 'Protein Rich') {
        matchesCat = recipe.ingredients?.some((i) =>
          ['Chicken', 'Beef', 'Egg', 'Fish', 'Pork', 'Salmon'].some((p) =>
            i.name.toLowerCase().includes(p.toLowerCase())
          )
        );
      } else if (selectedCategory === 'Vegetarian') {
        matchesCat = !recipe.ingredients?.some((i) =>
          ['Chicken', 'Beef', 'Pork', 'Fish', 'Salmon', 'Meat'].some((p) =>
            i.name.toLowerCase().includes(p.toLowerCase())
          )
        );
      } else if (selectedCategory === 'Sweet & Desserts') {
        matchesCat =
          recipe.name.toLowerCase().includes('cake') ||
          recipe.name.toLowerCase().includes('pancake') ||
          recipe.name.toLowerCase().includes('sweet') ||
          recipe.name.toLowerCase().includes('dessert');
      } else if (selectedCategory !== 'All') {
        matchesCat =
          recipe.description?.toLowerCase().includes(selectedCategory.toLowerCase()) ||
          recipe.name.toLowerCase().includes(selectedCategory.toLowerCase());
      }

      return matchesSearch && matchesTime && matchesCat;
    });
  }, [recipes, searchTerm, selectedCategory, maxCookTime]);

  const handleResetFilters = () => {
    setSearchTerm('');
    setSelectedCategory('All');
    setMaxCookTime(90);
  };

  const pantryCount = pantryIngredients.length;
  const shoppingCount = shoppingItems.filter((i) => !i.checked).length;

  return (
    <div className="space-y-10 pb-16">
      {/* Authenticated Kitchen Dashboard Strip */}
      {isAuthenticated && (
        <section className="relative overflow-hidden rounded-3xl bg-linear-to-br/srgb from-stone-900 via-stone-900 to-stone-950 text-white p-8 sm:p-10 shadow-2xl border border-stone-800">
          <div className="absolute -top-24 -right-24 w-80 h-80 bg-brand-500/15 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold uppercase tracking-wider text-brand-400">{t(`recipesPage.dashboard`)}</span>
                </div>
                <h1 className="text-2xl sm:text-4xl font-black text-white tracking-tight">
                  {t(`recipesPage.welcomeBack`)} {user?.username}! 👨‍🍳
                </h1>
                <p className="text-stone-300 text-sm sm:text-base mt-1">
                  {t(`recipesPage.welcomeSub`)}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <Link to="/ai-chef">
                  <StyledButton $variant="primary" $size="md" className="shadow-md shadow-brand-500/20">
                    <Sparkles className="w-4 h-4" />
                    <span>{t(`recipesPage.aiStudio`)}</span>
                  </StyledButton>
                </Link>
                <Link to="/pantry">
                  <StyledButton $variant="secondary" $size="md">
                    <Camera className="w-4 h-4 text-brand-500" />
                    <span>{t('recipesPage.scanFridge')}</span>
                  </StyledButton>
                </Link>
              </div>
            </div>

            {/* Quick Metrics Cards */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
              <Link
                to="/pantry"
                className="p-4 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all group"
              >
                <div className="flex items-center justify-between">
                  <ShoppingBag className="w-5 h-5 text-brand-400" />
                  <span className="text-xs font-bold text-stone-400 group-hover:text-white transition-colors">{t('recipesPage.manage')} →</span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-black text-white">{pantryCount}</div>
                  <div className="text-xs text-stone-300 font-medium">{t('recipesPage.pantryIngredients')}</div>
                </div>
              </Link>

              <Link
                to="/can-cook"
                className="p-4 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all group"
              >
                <div className="flex items-center justify-between">
                  <ChefHat className="w-5 h-5 text-emerald-400" />
                  <span className="text-xs font-bold text-stone-400 group-hover:text-white transition-colors">{t('recipesPage.cook')} →</span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-black text-white">
                    {pantryCount > 0 ? t('recipesPage.ready') : '0'}
                  </div>
                  <div className="text-xs text-stone-300 font-medium">{t('recipesPage.zeroWasteMatches')}</div>
                </div>
              </Link>

              <Link
                to="/ai-chef"
                className="p-4 rounded-2xl bg-white/5 hover:bg-white/10 border border-white/10 transition-all group"
              >
                <div className="flex items-center justify-between">
                  <Sparkles className="w-5 h-5 text-amber-400" />
                  <span className="text-xs font-bold text-stone-400 group-hover:text-white transition-colors">{t('recipesPage.create')} →</span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-black text-white">Live</div>
                  <div className="text-xs text-stone-300 font-medium">{t('recipesPage.liveGenerator')}</div>
                </div>
              </Link>

              <div className="p-4 rounded-2xl bg-white/5 border border-white/10">
                <div className="flex items-center justify-between">
                  <Clock className="w-5 h-5 text-sky-400" />
                  <span className="text-xs font-bold text-stone-400">{shoppingCount} {t('recipesPage.open')}</span>
                </div>
                <div className="mt-3">
                  <div className="text-2xl font-black text-white">{recipes.length}</div>
                  <div className="text-xs text-stone-300 font-medium">{t('recipesPage.recipesInCatalog')}</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Guest welcome strip */}
      {!isAuthenticated && (
        <section className="rounded-3xl bg-white border border-stone-200/80 shadow-card p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl sm:text-2xl font-black text-stone-900 tracking-tight">
              {t('recipesPage.guestTitle')} 🍳
            </h1>
            <p className="text-stone-500 text-sm mt-1">
              {t('recipesPage.guestSub')}
            </p>
          </div>
          <Link to="/" className="shrink-0">
            <StyledButton $variant="primary" $size="md">
              <Sparkles className="w-4 h-4" />
              <span>{t('recipesPage.tryAIDemo')}</span>
            </StyledButton>
          </Link>
        </section>
      )}

      {/* Main Recipe Explorer Catalog */}
      <section className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-stone-900 tracking-tight">
              {isAuthenticated ? t('recipesPage.recipeCatalog') : t('recipesPage.allRecipes')}
            </h2>
            <p className="text-stone-500 text-sm mt-1">
              {t('recipesPage.catalogSub')}
            </p>
          </div>
          <div className="text-xs font-semibold text-stone-500 bg-stone-100 px-3 py-1.5 rounded-xl self-start sm:self-auto">
            {t('recipesPage.showing')} <strong className="text-stone-800">{filteredRecipes.length}</strong> {t('recipesPage.of')}{' '}
            <strong>{recipes.length}</strong> recipes
          </div>
        </div>

        {/* Filters */}
        <RecipeFilter
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          maxCookTime={maxCookTime}
          onMaxCookTimeChange={setMaxCookTime}
          categories={['All', 'Quick (< 20m)', 'Protein Rich', 'Vegetarian', 'Sweet & Desserts']}
        />

        {/* Recipe Grid */}
        <RecipeGrid
          recipes={filteredRecipes}
          isLoading={isLoading}
          onResetFilters={handleResetFilters}
        />
      </section>
    </div>
  );
};
