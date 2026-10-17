import React from 'react';
import { Users, Minus, Plus } from 'lucide-react';

interface ServingScalerProps {
  currentServings: number;
  baseServings?: number;
  onChange: (newServings: number) => void;
}

export const scaleQuantity = (quantityStr: string, multiplier: number): string => {
  if (multiplier === 1 || !quantityStr) return quantityStr;

  // Match numbers and fractions (e.g., 2, 2.5, 1/2, 3/4)
  const fractionMatch = quantityStr.match(/^(\d+)\/(\d+)(.*)$/);
  if (fractionMatch) {
    const num = parseFloat(fractionMatch[1]);
    const den = parseFloat(fractionMatch[2]);
    const scaled = (num / den) * multiplier;
    return `${scaled % 1 === 0 ? scaled : scaled.toFixed(1)}${fractionMatch[3]}`;
  }

  const numberMatch = quantityStr.match(/^([\d.]+)(.*)$/);
  if (numberMatch) {
    const val = parseFloat(numberMatch[1]);
    if (!isNaN(val)) {
      const scaled = val * multiplier;
      const formatted = scaled % 1 === 0 ? scaled.toString() : scaled.toFixed(1);
      return `${formatted}${numberMatch[2]}`;
    }
  }

  return quantityStr;
};

export const ServingScaler: React.FC<ServingScalerProps> = ({
  currentServings,
  baseServings = 4,
  onChange,
}) => {
  const options = [1, 2, 4, 6, 8];

  return (
    <div className="flex flex-wrap items-center gap-2 bg-stone-100/90 p-1.5 px-3 rounded-2xl border border-stone-200/80 max-w-full overflow-hidden">
      <div className="flex items-center gap-1.5 text-stone-700 font-extrabold text-xs">
        <Users className="w-3.5 h-3.5 text-brand-500 shrink-0" />
        <span>Portions:</span>
      </div>

      {/* Stepper buttons */}
      <div className="flex items-center gap-1 bg-white/80 p-0.5 rounded-xl border border-stone-200/60">
        <button
          type="button"
          onClick={() => onChange(Math.max(1, currentServings - 1))}
          disabled={currentServings <= 1}
          className="w-6 h-6 rounded-lg bg-stone-50 hover:bg-stone-200 disabled:opacity-30 text-stone-700 flex items-center justify-center font-bold text-xs transition-colors"
          title="Decrease portion"
        >
          <Minus className="w-3 h-3" />
        </button>

        <span className="w-6 text-center font-black text-xs text-stone-900">
          {currentServings}
        </span>

        <button
          type="button"
          onClick={() => onChange(Math.min(12, currentServings + 1))}
          disabled={currentServings >= 12}
          className="w-6 h-6 rounded-lg bg-stone-50 hover:bg-stone-200 disabled:opacity-30 text-stone-700 flex items-center justify-center font-bold text-xs transition-colors"
          title="Increase portion"
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>

      {/* Quick multiplier pills with boundary wrap safety */}
      <div className="flex items-center gap-1 border-l border-stone-200 pl-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={`px-2 py-1 rounded-lg text-[11px] font-extrabold transition-all ${
 currentServings === opt
 ? 'bg-brand-500 text-white'
 : 'text-stone-600 hover:text-stone-900 hover:bg-stone-200/70'
 }`}
          >
            {opt}x
          </button>
        ))}
      </div>
    </div>
  );
};
