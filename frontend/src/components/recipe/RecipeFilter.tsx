import React from 'react';
import { Search, SlidersHorizontal, X, Clock, Flame } from 'lucide-react';

interface RecipeFilterProps {
  searchTerm: string;
  onSearchChange: (value: string) => void;
  selectedCategory: string;
  onCategoryChange: (cat: string) => void;
  maxCookTime: number;
  onMaxCookTimeChange: (time: number) => void;
  categories: string[];
}

export const RecipeFilter: React.FC<RecipeFilterProps> = ({
  searchTerm,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  maxCookTime,
  onMaxCookTimeChange,
  categories,
}) => {
  return (
    <div className="bg-white/85 backdrop-blur-xl border border-stone-200/80 rounded-3xl p-5 md:p-6 shadow-xs mb-8 space-y-5">
      {/* Top Search and Quick Stats */}
      <div className="flex flex-col sm:flex-row items-center gap-3">
        <div className="relative flex-1 w-full">
          <Search className="w-5 h-5 absolute left-3.5 top-1/2 -translate-y-1/2 text-stone-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by recipe name or ingredients (e.g. Pasta, Chicken, Chocolate)..."
            className="w-full pl-11 pr-10 py-3 bg-stone-50 border border-stone-200 rounded-2xl text-sm focus:outline-hidden focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 transition-all"
          />
          {searchTerm && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-700 p-1"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Max Cook Time Slider */}
        <div className="w-full sm:w-64 bg-stone-50 border border-stone-200 rounded-2xl px-4 py-2 flex flex-col justify-center">
          <div className="flex items-center justify-between text-xs font-semibold text-stone-600 mb-1">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-brand-500" /> Max Cook Time:
            </span>
            <span className="text-brand-600 font-bold">{maxCookTime >= 90 ? 'Any' : `${maxCookTime}m`}</span>
          </div>
          <input
            type="range"
            min={10}
            max={90}
            step={5}
            value={maxCookTime}
            onChange={(e) => onMaxCookTimeChange(Number(e.target.value))}
            className="w-full accent-brand-500 cursor-pointer h-1.5 bg-stone-200 rounded-lg"
          />
        </div>
      </div>

      {/* Category Pills */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <button
          onClick={() => onCategoryChange('All')}
          className={`px-4 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
 selectedCategory === 'All'
 ? 'bg-brand-500 text-white shadow-md shadow-brand-500/20'
 : 'bg-stone-100 text-stone-600 hover:bg-stone-200/70'
 }`}
        >
          🍳 All Dishes
        </button>

        {['Quick (< 20m)', 'Protein Rich', 'Vegetarian', 'Sweet & Desserts', 'Italian', 'Asian', 'Gourmet'].map((cat) => (
          <button
            key={cat}
            onClick={() => onCategoryChange(cat)}
            className={`px-3.5 py-2 rounded-xl text-xs font-semibold whitespace-nowrap transition-all ${
 selectedCategory === cat
 ? 'bg-stone-900 text-white shadow-xs'
 : 'bg-stone-100 text-stone-600 hover:bg-stone-200/70'
 }`}
          >
            {cat}
          </button>
        ))}
      </div>
    </div>
  );
};
