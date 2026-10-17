import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Sparkles, ChefHat, Clock, ArrowRight, RefreshCw, ShoppingBag } from 'lucide-react';
import { AISuggestedDish, AIProvider } from '../types/ai';
import { aiApi } from '../api/aiApi';
import { usePantry } from '../context/PantryContext';
import { useToast } from '../context/ToastContext';
import { StyledButton } from '../components/common/StyledButton';
import { StyledCard } from '../components/common/StyledCard';
import { LoadingChef } from '../components/common/LoadingChef';
import { AIProviderSwitcher } from '../components/common/AIProviderSwitcher';
import { assignUniqueDishPhotos } from '../utils/imageUtils';

export const AIChefPage: React.FC = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pantryIngredients, activeAIProvider, activeModel, setActiveAIProvider } = usePantry();
  const { error, aiToast } = useToast();

  const [selectedIngredients, setSelectedIngredients] = useState<string[]>(
    pantryIngredients.length > 0 ? pantryIngredients.map((i) => i.name) : ['Eggs', 'Flour', 'Milk', 'Tomato', 'Garlic']
  );
  const [customInput, setCustomInput] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [suggestions, setSuggestions] = useState<AISuggestedDish[]>([]);
  const [generatedProvider, setGeneratedProvider] = useState<string>('');
  // One distinct, stable photo per suggestion — even when several dish names
  // hit the same keyword (e.g. three different "pasta…" suggestions) or land
  // on the same fallback photo, no two cards on this page ever look alike.
  const dishPhotos = useMemo(() => assignUniqueDishPhotos(suggestions), [suggestions]);

  const toggleIngredient = (name: string) => {
    if (selectedIngredients.includes(name)) {
      setSelectedIngredients(selectedIngredients.filter((i) => i !== name));
    } else {
      setSelectedIngredients([...selectedIngredients, name]);
    }
  };

  const handleAddCustom = () => {
    if (customInput.trim() && !selectedIngredients.includes(customInput.trim())) {
      setSelectedIngredients([...selectedIngredients, customInput.trim()]);
      setCustomInput('');
    }
  };

  const handleUseAllPantry = () => {
    const allNames = pantryIngredients.map((i) => i.name);
    setSelectedIngredients(allNames);
  };

  const handleGenerate = async () => {
    if (selectedIngredients.length === 0) {
      error(t('aiChefPage.errSelect'), t('aiChefPage.errSelectTitle'));
      return;
    }

    setIsGenerating(true);
    setSuggestions([]);
    try {
      const res = await aiApi.getSuggestions({
        ingredients: selectedIngredients,
        provider: activeAIProvider,
        model: activeModel,
        force_refresh: true,
      });

      if (res.status === 'done' && res.recipes) {
        setSuggestions(res.recipes);
        setGeneratedProvider(res.provider || activeAIProvider);
        aiToast(t('aiChefPage.toastCrafted', { count: res.recipes.length }), t('aiChefPage.toastReadyTitle'));
      } else if (res.task_id) {
        // Poll celery task
        const pollInterval = setInterval(async () => {
          try {
            const taskRes = await aiApi.pollTaskStatus(res.task_id!);
            if (taskRes.status === 'done') {
              clearInterval(pollInterval);
              setSuggestions(taskRes.recipes || []);
              setIsGenerating(false);
              aiToast(t('aiChefPage.toastComplete'), t('aiChefPage.toastDoneTitle'));
            } else if (taskRes.status === 'error') {
              clearInterval(pollInterval);
              setIsGenerating(false);
              error(taskRes.error || t('aiChefPage.errHiccup'), t('aiChefPage.errGenTitle'));
            }
          } catch (e) {
            clearInterval(pollInterval);
            setIsGenerating(false);
          }
        }, 2000);
      }
    } catch (err: any) {
      error(err.message || t('aiChefPage.errHiccup'), t('aiChefPage.errGenTitle'));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="space-y-10 pb-16">
      {/* AI Studio Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-linear-to-r/srgb from-stone-900 via-stone-800 to-stone-950 text-white p-8 sm:p-12 shadow-2xl border border-stone-800">
        <div className="absolute top-0 right-0 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 max-w-3xl space-y-4">
          <span className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
            <Sparkles className="w-4 h-4 text-amber-400" />
            <span>{t('aiChefPage.badge')}</span>
          </span>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight">
            {t('aiChefPage.title')}
          </h1>

          <p className="text-stone-300 text-sm sm:text-base leading-relaxed max-w-2xl">
            {t('aiChefPage.subtitle')}
          </p>
        </div>
      </div>

      {/* Control Panel: Ingredient Selector & Prompt Form */}
      <div className="bg-white rounded-3xl border border-stone-200/90 p-6 md:p-8 shadow-xs space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="text-base font-bold text-stone-900">
              {t('aiChefPage.selectedCount', { count: selectedIngredients.length })}
            </h3>
            <p className="text-stone-500 text-xs mt-0.5">
              {t('aiChefPage.toggleHint')}
            </p>
          </div>

          {pantryIngredients.length > 0 && (
            <button
              onClick={handleUseAllPantry}
              className="text-xs font-semibold text-brand-600 hover:text-brand-700 flex items-center gap-1 self-start sm:self-auto"
            >
              <ShoppingBag className="w-3.5 h-3.5" />
              <span>{t('aiChefPage.selectAllPantry', { count: pantryIngredients.length })}</span>
            </button>
          )}
        </div>

        {/* Selected / Pantry Chips */}
        <div className="flex flex-wrap gap-2">
          {Array.from(new Set([...pantryIngredients.map((i) => i.name), ...selectedIngredients])).map(
            (name) => {
              const isSelected = selectedIngredients.includes(name);
              return (
                <button
                  key={name}
                  onClick={() => toggleIngredient(name)}
                  className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all flex items-center gap-1.5 ${
 isSelected
 ? 'bg-brand-500 text-white shadow-xs shadow-brand-500/30'
 : 'bg-stone-100 text-stone-600 hover:bg-stone-200'
 }`}
                >
                  <span>{name}</span>
                  <span className="text-[10px] opacity-80">{isSelected ? '✓' : '+'}</span>
                </button>
              );
            }
          )}
        </div>

        {/* Custom Ingredient Type Input */}
        <div className="flex items-center gap-2 max-w-md">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleAddCustom();
            }}
            placeholder={t('aiChefPage.customPlaceholder')}
            className="flex-1 px-3.5 py-2 text-xs bg-stone-50 border border-stone-200 rounded-xl focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
          <StyledButton $variant="secondary" $size="sm" onClick={handleAddCustom}>
            {t('aiChefPage.add')}
          </StyledButton>
        </div>

        {/* Action Trigger */}
        <div className="pt-4 border-t border-stone-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="text-xs text-stone-500 flex items-center gap-1.5 font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>
              {t('aiChefPage.engineLabel')}{' '}
              <strong>{activeAIProvider === 'gemini' ? t('aiChefPage.engineGemini', { model: activeModel }) : t('aiChefPage.engineLocal')}</strong>
            </span>
          </div>

          <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4">
            <AIProviderSwitcher />

            <StyledButton
              $variant="primary"
              $size="lg"
              onClick={handleGenerate}
              disabled={isGenerating || selectedIngredients.length === 0}
              className="w-full sm:w-auto"
            >
              {isGenerating ? (
                <>
                  <RefreshCw className="w-5 h-5 animate-spin" />
                  <span>{t('aiChefPage.generating')}</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-5 h-5" />
                  <span>{t('aiChefPage.generate')}</span>
                </>
              )}
            </StyledButton>
          </div>
        </div>
      </div>

      {/* Generation Results */}
      {isGenerating && <LoadingChef provider={activeAIProvider} />}

      {!isGenerating && suggestions.length > 0 && (
        <section className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-extrabold text-stone-900 tracking-tight flex items-center gap-2">
                <ChefHat className="w-6 h-6 text-brand-500" />
                <span>{t('aiChefPage.creationsTitle')}</span>
              </h2>
              <p className="text-stone-500 text-xs mt-0.5">
                {t('aiChefPage.creationsSub')}
              </p>
            </div>
            <span className="text-xs font-bold bg-amber-100 text-amber-800 px-3 py-1 rounded-full">
              {t('aiChefPage.dishesReady', { count: suggestions.length })}
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {suggestions.map((dish, index) => {
              const detailUrl = `/ai-recipe/${encodeURIComponent(dish.name)}?provider=${activeAIProvider}${activeModel ? `&model=${encodeURIComponent(activeModel)}` : ''}`;
              return (
                <StyledCard
                  key={index}
                  $interactive
                  $padded={false}
                  onClick={() => navigate(detailUrl)}
                  className="group flex flex-col justify-between h-full bg-white cursor-pointer hover:shadow-xl transition-all duration-300 transform hover:-translate-y-1"
                >
                  {/* Dish Photo — one unique photo per dish on the page */}
                  <div className="relative h-48 w-full overflow-hidden bg-stone-100">
                    <img
                      src={dishPhotos[index]}
                      alt={dish.name}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                      onError={(e) => {
                        const fallback = dishPhotos[(index + 1) % dishPhotos.length];
                        if (fallback && (e.target as HTMLImageElement).src !== fallback) {
                          (e.target as HTMLImageElement).src = fallback;
                        }
                      }}
                    />
                    <div className="absolute inset-0 bg-linear-to-t/srgb from-stone-900/70 via-transparent to-transparent opacity-80" />

                    <div className="absolute top-3 left-3 flex gap-2">
                      <span className="bg-stone-900/80 backdrop-blur-md text-white text-[11px] font-bold px-2.5 py-0.5 rounded-full">
                        {dish.cuisine || t('aiChefPage.gourmet')}
                      </span>
                      {dish.difficulty && (
                        <span className="bg-emerald-500/90 text-white text-[11px] font-bold px-2.5 py-0.5 rounded-full">
                          {dish.difficulty}
                        </span>
                      )}
                    </div>

                    <div className="absolute bottom-3 left-3 right-3">
                      <h3 className="text-lg font-bold text-white leading-tight drop-shadow-xs group-hover:text-amber-200 transition-colors">
                        {dish.name}
                      </h3>
                    </div>
                  </div>

                  {/* Dish Description */}
                  <div className="p-5 flex-1 flex flex-col justify-between">
                    <p className="text-stone-600 text-sm leading-relaxed mb-4">
                      {dish.short_description}
                    </p>

                    <div className="pt-3 border-t border-stone-100 flex items-center justify-between">
                      <span className="text-xs text-stone-500 font-semibold flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-stone-400" />
                        <span>{dish.prep_time || '25 mins'}</span>
                      </span>

                      <div className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-600 group-hover:text-brand-700 group-hover:translate-x-1 transition-transform">
                        <span>{t('aiChefPage.cookFullRecipe')}</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  </div>
                </StyledCard>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
};
