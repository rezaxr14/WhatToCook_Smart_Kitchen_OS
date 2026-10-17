import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ChefHat, Sparkles } from 'lucide-react';
import { StyledCard } from './StyledCard';

interface LoadingChefProps {
  message?: string;
  provider?: string;
}

const COOKING_STEPS = [
  'Checking your pantry ingredients...',
  'Pairing aromatics and flavor profiles...',
  'Simmering creative culinary concepts...',
  'Balancing textures, spices, and nutrition...',
  'Plating up delicious recipe suggestions...',
];

export const LoadingChef: React.FC<LoadingChefProps> = ({ message, provider = 'gemini' }) => {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev + 1) % COOKING_STEPS.length);
    }, 2400);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center p-8 text-center max-w-md mx-auto">
      <StyledCard $glow className="w-full p-8 flex flex-col items-center">
        {/* Animated Pan and Steam */}
        <div className="relative mb-6">
          <motion.div
            animate={{
              y: [0, -8, 0],
              rotate: [0, -3, 3, 0],
            }}
            transition={{
              duration: 2,
              repeat: Infinity,
              ease: 'easeInOut',
            }}
            className="w-24 h-24 rounded-full bg-linear-to-tr/srgb from-brand-500 to-amber-400 flex items-center justify-center shadow-lg shadow-brand-500/30 text-white relative z-10"
          >
            <ChefHat className="w-12 h-12" />
          </motion.div>

          {/* Floating Steam Bubbles */}
          <motion.div
            animate={{ y: [-10, -30], opacity: [0.8, 0], scale: [0.8, 1.4] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'easeOut', delay: 0.2 }}
            className="absolute -top-2 left-4 text-orange-400 font-bold text-xs pointer-events-none"
          >
            ✨
          </motion.div>
          <motion.div
            animate={{ y: [-10, -35], opacity: [0.8, 0], scale: [0.8, 1.6] }}
            transition={{ duration: 1.8, repeat: Infinity, ease: 'easeOut', delay: 0.7 }}
            className="absolute -top-4 right-4 text-amber-500 font-bold text-sm pointer-events-none"
          >
            🌿
          </motion.div>
          <motion.div
            animate={{ y: [-10, -28], opacity: [0.8, 0], scale: [0.8, 1.3] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut', delay: 1.1 }}
            className="absolute -top-6 left-10 text-orange-400 font-bold text-xs pointer-events-none"
          >
            🍳
          </motion.div>
        </div>

        {/* Status text */}
        <h3 className="font-extrabold text-stone-900 text-lg sm:text-xl flex items-center justify-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-500 animate-spin" style={{ animationDuration: '4s' }} />
          <span>AI Chef is Cooking</span>
        </h3>

        <motion.p
          key={stepIndex}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          className="text-stone-600 text-sm font-medium min-h-6"
        >
          {message || COOKING_STEPS[stepIndex]}
        </motion.p>

        {/* Progress Dots */}
        <div className="flex gap-2 mt-5">
          {COOKING_STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 rounded-full transition-all duration-500 ${
 i === stepIndex ? 'w-6 bg-brand-500' : 'w-1.5 bg-stone-200'
 }`}
            />
          ))}
        </div>
      </StyledCard>
    </div>
  );
};
