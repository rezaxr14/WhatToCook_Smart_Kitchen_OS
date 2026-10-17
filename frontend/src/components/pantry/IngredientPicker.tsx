import React, { useState, useMemo } from 'react';
import { Search, Plus, Check, Sparkles, Wand2, Apple } from 'lucide-react';
import { Ingredient } from '../../types/ingredient';
import { StyledButton } from '../common/StyledButton';

interface IngredientPickerProps {
  availableIngredients: Ingredient[];
  onAdd: (ingredient: Ingredient | string) => void;
  onAddMultiple?: (ids: number[]) => void;
}

const POPULAR_BUNDLE = [
  'Eggs',
  'Flour',
  'Milk',
  'Butter',
  'Cheddar Cheese',
  'Chicken Breast',
  'Tomato',
  'Garlic',
  'Onion',
  'Rice',
  'Pasta',
  'Olive Oil',
];

const CATEGORIES = [
  'All',
  'Produce',
  'Dairy & Eggs',
  'Meat & Seafood',
  'Grains & Pasta',
  'Pantry & Spices',
];

export const IngredientPicker: React.FC<IngredientPickerProps> = ({
  availableIngredients,
  onAdd,
  onAddMultiple,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('All');

  // Filtered ingredients
  const filtered = useMemo(() => {
    return availableIngredients.filter((ing) => {
      const matchesSearch = ing.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesCategory = selectedCategory === 'All' || ing.category === selectedCategory;
      return matchesSearch && matchesCategory;
    });
  }, [availableIngredients, searchTerm, selectedCategory]);

  const handleCustomAdd = () => {
    if (searchTerm.trim()) {
      onAdd(searchTerm.trim());
      setSearchTerm('');
    }
  };

  const handleAddBundle = () => {
    if (!onAddMultiple) return;
    const matchingIds = availableIngredients
      .filter((i) => POPULAR_BUNDLE.some((b) => b.toLowerCase() === i.name.toLowerCase()))
      .map((i) => i.id);
    if (matchingIds.length > 0) {
      onAddMultiple(matchingIds);
    }
  };

  return (
    <div className="bg-white rounded-3xl border border-stone-200/90 p-6 shadow-xs space-y-5">
      {/* Header and Quick Bundle Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="font-extrabold text-stone-900 text-base">Ingredient Catalog</h3>
            <span className="bg-stone-100 border border-stone-200 text-stone-600 font-bold text-xs px-2.5 py-0.5 rounded-full">
              {availableIngredients.length} Items
            </span>
          </div>
          <p className="text-stone-500 text-xs mt-0.5">
            Select items to add to your kitchen shelf or type a custom ingredient.
          </p>
        </div>

        {onAddMultiple && (
          <button
            type="button"
            onClick={handleAddBundle}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-bold hover:bg-amber-100 transition-colors cursor-pointer"
          >
            <Wand2 className="w-3.5 h-3.5 text-amber-600" />
            <span>+ Add Chef's Starter Kit</span>
          </button>
        )}
      </div>

      {/* Category Filter Pills */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
        {CATEGORIES.map((cat) => {
          const isSelected = selectedCategory === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition-all cursor-pointer ${
 isSelected
 ? 'bg-stone-900 text-white'
 : 'bg-stone-100 text-stone-600 hover:bg-stone-200/80 hover:text-stone-900'
 }`}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* Search Input & Custom Add */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleCustomAdd();
            }}
            placeholder="Search ingredients (e.g. Avocado, Ice Cream, Chicken, Mozzarella)..."
            className="w-full pl-10 pr-4 py-2.5 bg-stone-50 border border-stone-200 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
          />
        </div>

        {searchTerm.trim() && (
          <StyledButton $variant="primary" $size="sm" onClick={handleCustomAdd}>
            <Plus className="w-4 h-4" />
            <span>Add Custom</span>
          </StyledButton>
        )}
      </div>

      {/* Visual Ingredients Grid with High-Res Thumbnails (Scrolls naturally with page) */}
      <div className="space-y-2">
        {filtered.length > 0 ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {filtered.map((ing) => (
              <button
                key={ing.id}
                type="button"
                onClick={() => onAdd(ing)}
                style={{ height: '180px' }}
                className="group relative flex flex-col justify-between w-full p-2.5 rounded-2xl border border-stone-200 bg-stone-50/70 hover:bg-white hover:border-brand-400 hover:shadow-md text-stone-800 text-left transition-all cursor-pointer overflow-hidden"
              >
                {/* Photo Thumbnail with Exact Uniform Fixed Dimensions */}
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

                  <span className="absolute bottom-1.5 right-1.5 w-6 h-6 rounded-lg bg-white/90 group-hover:bg-brand-500 group-hover:text-white text-stone-700 flex items-center justify-center transition-colors">
                    <Plus className="w-3.5 h-3.5" />
                  </span>
                </div>

                <div className="w-full min-w-0 pt-1.5 flex flex-col justify-end">
                  <div className="font-bold text-xs text-stone-900 truncate capitalize">
                    {ing.name}
                  </div>
                  <div className="text-[10px] text-stone-500 truncate mt-0.5">
                    {ing.category || 'General'}
                  </div>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <div className="py-12 text-center text-stone-500 text-xs">
            No matching catalog ingredients.{' '}
            {searchTerm && (
              <span
                onClick={handleCustomAdd}
                className="text-brand-600 font-bold cursor-pointer hover:underline block mt-1"
              >
                Click here to add "{searchTerm}" as a custom ingredient.
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
