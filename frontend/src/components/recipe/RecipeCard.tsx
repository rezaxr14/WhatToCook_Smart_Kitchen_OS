import React from 'react';
import { Link } from 'react-router-dom';
import { Clock, ChefHat, Check, AlertCircle, ArrowRight } from 'lucide-react';
import { Recipe, MatchedRecipe } from '../../types/recipe';
import { StyledCard } from '../common/StyledCard';
import { Badge } from '../common/Badge';

interface RecipeCardProps {
  recipe: Recipe | MatchedRecipe;
  isMatched?: boolean;
}

// Distinct, self-hosted fallbacks — if a photo ever fails to load, each card
// still gets its own image (never a shared one, so a grid can't look alike).
const FALLBACK_POOL = [
  '/media/recipes/carbonara.jpg',
  '/media/recipes/avocado_toast.jpg',
  '/media/recipes/pancakes.jpg',
  '/media/recipes/garlic_shrimp.jpg',
  '/media/recipes/omelette.jpg',
  '/media/recipes/penne_pomodoro.jpg',
  '/media/recipes/grilled_cheese.jpg',
];

const fallbackFor = (name: string): string => {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return FALLBACK_POOL[Math.abs(h) % FALLBACK_POOL.length];
};

export const RecipeCard: React.FC<RecipeCardProps> = ({ recipe, isMatched }) => {
  const matchedRecipe = recipe as MatchedRecipe;
  const hasMatchInfo = isMatched && matchedRecipe.match_percentage !== undefined;

  const getImageUrl = () => {
    if (recipe.image_url) return recipe.image_url;
    if (recipe.image) {
      if (recipe.image.startsWith('http') || recipe.image.startsWith('/')) {
        return recipe.image;
      }
      return `/media/${recipe.image}`;
    }
    return '/media/recipes/default.png';
  };
  const fallbackUrl = fallbackFor(recipe.name);

  return (
    <StyledCard $interactive $padded={false} className="group flex flex-col h-full bg-white">
      {/* Clickable Image Banner */}
      <Link to={`/recipe/${recipe.id}`} className="relative h-52 w-full overflow-hidden bg-stone-100 block cursor-pointer">
        <img
          src={getImageUrl()}
          alt={recipe.name}
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-105"
          onError={(e) => {
            const t = e.target as HTMLImageElement;
            if (t.src !== fallbackUrl) t.src = fallbackUrl;
          }}
        />
        <div className="absolute inset-0 bg-linear-to-t/srgb from-stone-900/70 via-stone-900/20 to-transparent opacity-90 transition-opacity group-hover:opacity-100" />

        {/* Top Badges */}
        <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-2">
          {recipe.cooking_time ? (
            <span className="bg-stone-900/80 backdrop-blur-md text-white text-xs font-semibold px-2.5 py-1 rounded-full flex items-center gap-1 shadow-xs">
              <Clock className="w-3.5 h-3.5 text-amber-300" />
              <span>{recipe.cooking_time} mins</span>
            </span>
          ) : (
            <span />
          )}

          {hasMatchInfo && (
            <span
              className={`text-xs font-bold px-2.5 py-1 rounded-full backdrop-blur-md shadow-xs flex items-center gap-1 ${
 matchedRecipe.missing_count === 0
 ? 'bg-emerald-500/90 text-white'
 : 'bg-amber-500/90 text-white'
 }`}
            >
              {matchedRecipe.missing_count === 0 ? (
                <>
                  <Check className="w-3.5 h-3.5" /> 100% Match
                </>
              ) : (
                <>
                  <AlertCircle className="w-3.5 h-3.5" /> {matchedRecipe.match_percentage}% Match
                </>
              )}
            </span>
          )}
        </div>

        {/* Title overlay in image */}
        <div className="absolute bottom-3 left-3 right-3">
          <h3 className="text-lg font-bold text-white leading-tight drop-shadow-xs group-hover:text-amber-200 transition-colors">
            {recipe.name}
          </h3>
        </div>
      </Link>

      {/* Card Content */}
      <div className="p-5 flex-1 flex flex-col justify-between">
        <div>
          <p className="text-stone-600 text-sm line-clamp-2 mb-4 leading-relaxed">
            {recipe.description || 'Delicious home-cooked recipe with vibrant fresh ingredients.'}
          </p>

          {/* Missing items warning if in CanCook mode */}
          {hasMatchInfo && matchedRecipe.missing_count > 0 && (
            <div className="mb-4 p-2.5 rounded-xl bg-amber-50/80 border border-amber-200/70 text-xs text-amber-900 flex items-start gap-1.5">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold">Missing ({matchedRecipe.missing_count}): </span>
                <span>{matchedRecipe.missing_ingredients.join(', ')}</span>
              </div>
            </div>
          )}

          {/* Ingredients Pill Tags */}
          <div className="mb-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-stone-500 mb-2">
              Key Ingredients ({recipe.ingredients?.length || 0})
            </div>
            <div className="flex flex-wrap gap-1.5">
              {recipe.ingredients?.slice(0, 4).map((ing) => (
                <span
                  key={ing.id}
                  className="text-xs px-2.5 py-0.5 rounded-lg bg-stone-100 text-stone-700 font-medium"
                >
                  {ing.name}
                </span>
              ))}
              {(recipe.ingredients?.length || 0) > 4 && (
                <span className="text-xs px-2 py-0.5 rounded-lg bg-stone-100 text-stone-500 font-medium">
                  +{recipe.ingredients.length - 4} more
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Action Link */}
        <div className="pt-3 border-t border-stone-100 flex items-center justify-between">
          <Link
            to={`/recipe/${recipe.id}`}
            className="w-full flex items-center justify-center gap-2 py-2 px-4 rounded-xl bg-brand-50 hover:bg-brand-500 text-brand-700 hover:text-white font-semibold text-sm transition-all group-hover:shadow-xs"
          >
            <ChefHat className="w-4 h-4" />
            <span>View & Cook Recipe</span>
            <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
          </Link>
        </div>
      </div>
    </StyledCard>
  );
};
