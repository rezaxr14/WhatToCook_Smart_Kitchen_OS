import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, Plus, ShoppingBag, X, Camera, Apple } from 'lucide-react';
import { Ingredient } from '../../types/ingredient';
import { StyledCard } from '../common/StyledCard';
import { StyledButton } from '../common/StyledButton';

interface PantryShelfProps {
  ingredients: Ingredient[];
  onRemove: (id: number) => void;
  onClear: () => void;
  onOpenPicker?: () => void;
  onOpenScanner?: () => void;
}

export const PantryShelf: React.FC<PantryShelfProps> = ({
  ingredients,
  onRemove,
  onClear,
  onOpenPicker,
  onOpenScanner,
}) => {
  if (ingredients.length === 0) {
    return (
      <StyledCard className="p-10 text-center border-dashed border-2 border-stone-300 bg-white/60">
        <div className="w-16 h-16 rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mx-auto mb-4">
          <ShoppingBag className="w-8 h-8" />
        </div>
        <h3 className="text-xl font-bold text-stone-900 mb-2">Your pantry is currently empty</h3>
        <p className="text-stone-500 text-sm max-w-md mx-auto mb-6">
          Add the ingredients you have at home to see what recipes you can cook immediately, or snap a photo of your fridge for instant AI detection.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          {onOpenScanner && (
            <button
              onClick={onOpenScanner}
              className="flex items-center gap-2 px-5 py-2.5 rounded-2xl bg-linear-to-r/srgb from-amber-400 to-brand-500 text-stone-950 font-extrabold text-sm shadow-md hover:scale-105 transition-all"
            >
              <Camera className="w-4 h-4" />
              <span>📸 Scan Fridge Photo</span>
            </button>
          )}

          {onOpenPicker && (
            <StyledButton $variant="secondary" onClick={onOpenPicker}>
              <Plus className="w-4 h-4" />
              <span>Add from Catalog</span>
            </StyledButton>
          )}
        </div>
      </StyledCard>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header & Clear */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-stone-800">
            Stocked Ingredients ({ingredients.length})
          </span>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-extrabold">
            Live Kitchen
          </span>
        </div>

        <div className="flex items-center gap-4">
          {onOpenScanner && (
            <button
              onClick={onOpenScanner}
              className="text-xs text-brand-600 hover:text-brand-700 font-bold flex items-center gap-1.5 transition-colors"
            >
              <Camera className="w-3.5 h-3.5" />
              <span>Scan More</span>
            </button>
          )}

          <button
            onClick={onClear}
            className="text-xs text-stone-500 hover:text-rose-600 font-semibold flex items-center gap-1 transition-colors cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Pantry</span>
          </button>
        </div>
      </div>

      {/* Grid of stocked items with high-res food thumbnails */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <AnimatePresence>
          {ingredients.map((ing) => (
            <motion.div
              key={ing.id}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              style={{ height: '180px' }}
              className="group relative bg-white border border-stone-200/90 rounded-2xl p-2.5 hover:shadow-md hover:border-brand-400 transition-all flex flex-col justify-between w-full overflow-hidden"
            >
              {/* Image Thumbnail with Uniform Fixed Dimensions */}
              <div
                style={{ height: '96px', width: '100%' }}
                className="relative w-full rounded-xl overflow-hidden bg-stone-100 shrink-0"
              >
                {ing.image_url ? (
                  <img
                    src={ing.image_url}
                    alt={ing.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    className="w-full h-full object-cover transition-transform duration-300"
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=400&q=80';
                    }}
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center bg-stone-100 text-stone-400">
                    <Apple className="w-6 h-6" />
                  </div>
                )}

                {/* Remove button over image */}
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(ing.id);
                  }}
                  className="absolute top-1.5 right-1.5 w-6 h-6 rounded-full bg-stone-900/60 hover:bg-rose-600 text-white flex items-center justify-center transition-colors shadow-xs cursor-pointer"
                  title="Remove from pantry"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="w-full min-w-0 pt-1.5 flex flex-col justify-end">
                <div className="font-bold text-stone-900 text-xs truncate capitalize" title={ing.name}>
                  {ing.name}
                </div>
                <div className="flex items-center justify-between text-[10px] text-stone-500 mt-0.5">
                  <span className="truncate text-stone-400">{ing.category || 'General'}</span>
                  {ing.calories_per_100g !== null && ing.calories_per_100g !== undefined && (
                    <span className="font-semibold text-amber-700">{ing.calories_per_100g} kcal</span>
                  )}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
};
