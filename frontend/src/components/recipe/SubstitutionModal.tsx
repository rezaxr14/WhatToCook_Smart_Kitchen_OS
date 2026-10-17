import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, X, ArrowRight, Check, Search, ChefHat } from 'lucide-react';

interface SubstitutionModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialIngredient?: string;
}

const COMMON_SUBSTITUTES: Record<string, { substitute: string; ratio: string; notes: string }[]> = {
  butter: [
    { substitute: 'Olive Oil', ratio: '3/4 cup oil per 1 cup butter', notes: 'Best for sautéing and savory cooking.' },
    { substitute: 'Greek Yogurt', ratio: '1:1 ratio', notes: 'Adds moisture with less fat in baking.' },
    { substitute: 'Coconut Oil', ratio: '1:1 ratio', notes: 'Great 1:1 substitute in high-heat frying.' },
  ],
  eggs: [
    { substitute: 'Flaxseed Meal + Water', ratio: '1 tbsp flax + 3 tbsp water', notes: 'Let rest 5 mins to gel. Perfect for baking.' },
    { substitute: 'Mashed Banana / Applesauce', ratio: '1/4 cup per egg', notes: 'Adds natural sweetness in pancakes and muffins.' },
    { substitute: 'Silken Tofu', ratio: '1/4 cup blended tofu per egg', notes: 'Neutral taste, ideal for dense bakes.' },
  ],
  milk: [
    { substitute: 'Oat Milk / Almond Milk', ratio: '1:1 ratio', notes: 'Direct dairy-free substitute.' },
    { substitute: 'Water + Butter', ratio: '1 cup water + 1 tbsp butter', notes: 'Works in a pinch for cooking batters.' },
  ],
  'heavy cream': [
    { substitute: 'Milk + Melted Butter', ratio: '3/4 cup milk + 1/4 cup melted butter', notes: 'Standard culinary stand-in.' },
    { substitute: 'Coconut Cream', ratio: '1:1 ratio', notes: 'Rich and velvety, perfect for curries and soups.' },
  ],
  garlic: [
    { substitute: 'Garlic Powder', ratio: '1/8 tsp powder per 1 fresh clove', notes: 'Concentrated flavor.' },
    { substitute: 'Shallots or Chives', ratio: '1/2 shallot per clove', notes: 'Mild, sweet allium aroma.' },
  ],
  parmesan: [
    { substitute: 'Pecorino Romano', ratio: '1:1 ratio', notes: 'Slightly saltier, fantastic in pasta.' },
    { substitute: 'Nutritional Yeast', ratio: '1:1 ratio', notes: 'Vegan savory cheesy substitute.' },
  ],
  lemon: [
    { substitute: 'Apple Cider Vinegar / White Wine', ratio: '1/2 tsp vinegar per 1 tsp lemon juice', notes: 'Provides necessary acidity.' },
    { substitute: 'Lime Juice', ratio: '1:1 ratio', notes: 'Closest citrus flavor match.' },
  ],
};

export const SubstitutionModal: React.FC<SubstitutionModalProps> = ({
  isOpen,
  onClose,
  initialIngredient = '',
}) => {
  const [searchTerm, setSearchTerm] = useState(initialIngredient);

  if (!isOpen) return null;

  const query = searchTerm.toLowerCase().trim();
  const matchedKey = Object.keys(COMMON_SUBSTITUTES).find((k) => query.includes(k) || k.includes(query));
  const results = matchedKey ? COMMON_SUBSTITUTES[matchedKey] : null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-950/70 backdrop-blur-md overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative w-full max-w-lg bg-white rounded-3xl border border-stone-200 shadow-2xl overflow-hidden my-8"
      >
        {/* Header */}
        <div className="bg-linear-to-r/srgb from-stone-900 via-stone-850 to-stone-950 p-6 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-lg text-white">Smart Substitutions</h3>
                <span className="bg-amber-400 text-stone-950 font-black text-[10px] uppercase px-2 py-0.5 rounded-full">
                  AI Chef
                </span>
              </div>
              <p className="text-stone-400 text-xs mt-0.5">
                Missing an ingredient? Find instant culinary swaps.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-stone-300 hover:text-white flex items-center justify-center transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Search Bar */}
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-stone-400" />
            <input
              type="text"
              placeholder="Search missing item (e.g. Butter, Eggs, Heavy Cream, Garlic)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-11 pr-4 py-3 rounded-2xl border border-stone-200 text-sm font-medium focus:outline-hidden focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500"
            />
          </div>

          {/* Quick Select Tags */}
          <div className="flex flex-wrap gap-1.5">
            {['Butter', 'Eggs', 'Milk', 'Heavy Cream', 'Garlic', 'Parmesan', 'Lemon'].map((tag) => (
              <button
                key={tag}
                onClick={() => setSearchTerm(tag)}
                className={`px-3 py-1 rounded-xl text-xs font-bold transition-all ${
 searchTerm.toLowerCase() === tag.toLowerCase()
 ? 'bg-amber-500 text-white'
 : 'bg-stone-100 hover:bg-stone-200 text-stone-700'
 }`}
              >
                {tag}
              </button>
            ))}
          </div>

          {/* Results Area */}
          <div className="space-y-3">
            {results ? (
              <div className="space-y-3">
                <div className="text-xs font-extrabold text-stone-400 uppercase tracking-wider">
                  Top Swaps for {matchedKey?.toUpperCase()}
                </div>
                {results.map((sub, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-2xl bg-amber-50/50 border border-amber-200/60 space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-extrabold text-stone-900 text-sm flex items-center gap-2">
                        <Check className="w-4 h-4 text-emerald-500" />
                        {sub.substitute}
                      </span>
                      <span className="text-xs font-bold text-amber-700 bg-amber-100/80 px-2.5 py-0.5 rounded-full">
                        {sub.ratio}
                      </span>
                    </div>
                    <p className="text-xs text-stone-600 pl-6">{sub.notes}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 rounded-2xl bg-stone-50 border border-stone-200 text-center space-y-2">
                <ChefHat className="w-8 h-8 text-stone-300 mx-auto" />
                <p className="text-sm font-bold text-stone-700">
                  {searchTerm ? `AI Chef Tip for "${searchTerm}"` : 'Type an ingredient above'}
                </p>
                <p className="text-xs text-stone-500 max-w-sm mx-auto">
                  In cooking, acidic items can usually be swapped with vinegar or wine, fats with olive oil or butter, and aromatics with shallots or dried powders.
                </p>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </div>
  );
};
