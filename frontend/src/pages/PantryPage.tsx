import React, { useState } from 'react';
import { Link } from 'react-router';
import { ShoppingBag, ChefHat, Sparkles, Camera } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { usePantry } from '../context/PantryContext';
import { PantryShelf } from '../components/pantry/PantryShelf';
import { IngredientPicker } from '../components/pantry/IngredientPicker';
import { StyledButton } from '../components/common/StyledButton';

export const PantryPage: React.FC = () => {
  const { t } = useTranslation();
  const {
    pantryIngredients,
    availableIngredients,
    addIngredient,
    addMultipleIngredients,
    removeIngredient,
    clearPantry,
    openScanner,
  } = usePantry();

  const [isConfirmingClear, setIsConfirmingClear] = useState(false);

  const handleClearWithConfirm = () => {
    if (isConfirmingClear) {
      clearPantry();
      setIsConfirmingClear(false);
    } else {
      setIsConfirmingClear(true);
      setTimeout(() => setIsConfirmingClear(false), 4000);
    }
  };

  return (
    <div className="space-y-8 pb-16">
      {/* Page Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-linear-to-r/srgb from-stone-900 via-stone-850 to-stone-950 text-white rounded-3xl p-6 sm:p-8 shadow-xl relative overflow-hidden">
        <div className="absolute top-0 right-0 w-80 h-80 bg-brand-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-2 text-amber-400 text-xs font-bold uppercase tracking-wider mb-1">
            <ShoppingBag className="w-4 h-4" />
            <span>{t('pantryPage.inventoryBadge')}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight">{t('pantryPage.title')}</h1>
          <p className="text-stone-400 text-sm mt-1 max-w-xl">
            {t('pantryPage.subtitle')}
          </p>
        </div>

        <div className="relative z-10 flex flex-wrap items-center gap-3">
          {/* Gemini Vision Fridge Scanner CTA */}
          <button
            onClick={openScanner}
            className="flex items-center gap-2 px-4 py-2.5 rounded-2xl bg-linear-to-r/srgb from-amber-400 to-brand-500 text-stone-950 font-extrabold text-xs shadow-lg shadow-brand-500/20 hover:scale-105 transition-all cursor-pointer"
          >
            <Camera className="w-4 h-4" />
            <span>{t('pantryPage.scanFridgePhoto')}</span>
          </button>

          <Link to="/can-cook">
            <StyledButton $variant="primary" $size="md">
              <ChefHat className="w-4 h-4" />
              <span>{t('pantryPage.seeMatching')}</span>
            </StyledButton>
          </Link>

          <Link to="/ai-chef">
            <StyledButton $variant="sage" $size="md">
              <Sparkles className="w-4 h-4" />
              <span>{t('pantryPage.aiChefIdeas')}</span>
            </StyledButton>
          </Link>
        </div>
      </div>

      {/* Pantry Shelf Section */}
      <div className="bg-white/80 backdrop-blur-xl border border-stone-200/90 rounded-3xl p-6 shadow-xs">
        <PantryShelf
          ingredients={pantryIngredients}
          onRemove={removeIngredient}
          onClear={handleClearWithConfirm}
          onOpenScanner={openScanner}
        />

        {isConfirmingClear && (
          <div className="mt-3 p-3 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold flex items-center justify-between">
            <span>{t('pantryPage.confirmClear')}</span>
            <div className="flex gap-2">
              <button
                onClick={clearPantry}
                className="px-3 py-1 bg-rose-600 text-white rounded-lg font-bold hover:bg-rose-700 transition-colors"
              >
                {t('pantryPage.yesClearAll')}
              </button>
              <button
                onClick={() => setIsConfirmingClear(false)}
                className="px-3 py-1 bg-stone-200 text-stone-700 rounded-lg hover:bg-stone-300 transition-colors"
              >
                {t('pantryPage.cancel')}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Add New Ingredients Section */}
      <IngredientPicker
        availableIngredients={availableIngredients}
        onAdd={addIngredient}
        onAddMultiple={addMultipleIngredients}
      />
    </div>
  );
};
