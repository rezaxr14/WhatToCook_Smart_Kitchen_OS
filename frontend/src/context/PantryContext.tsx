import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, ReactNode } from 'react';
import { Ingredient } from '../types/ingredient';
import { AIProvider, AIProvidersResponse } from '../types/ai';
import { pantryApi } from '../api/pantryApi';
import { recipeApi } from '../api/recipeApi';
import { aiApi } from '../api/aiApi';
import { useAuth } from './AuthContext';
import { useToast } from './ToastContext';

export interface ScanSummary {
  names: string[];
  count: number;
  at: number;
}

interface PantryContextValue {
  pantryIngredients: Ingredient[];
  availableIngredients: Ingredient[];
  allIngredients: Ingredient[];
  isLoading: boolean;
  activeAIProvider: AIProvider;
  activeModel: string;
  availableModels: Array<{ id: string; displayName?: string; name?: string; description?: string }>;
  rateLimitedModels: string[];
  aiProvidersInfo: AIProvidersResponse | null;
  setActiveAIProvider: (provider: AIProvider) => void;
  setActiveModel: (model: string) => void;
  markModelRateLimited: (modelId: string) => void;
  handleRateLimitedModels: (models: string[]) => void;
  addIngredient: (ingredient: Ingredient | number | string) => Promise<void>;
  addMultipleIngredients: (ids: number[]) => Promise<void>;
  removeIngredient: (ingredientId: number) => Promise<void>;
  clearPantry: () => Promise<void>;
  isInPantry: (ingredientId: number) => boolean;
  refreshPantry: () => Promise<void>;
  isScannerOpen: boolean;
  openScanner: () => void;
  closeScanner: () => void;
  lastScanResult: ScanSummary | null;
  setLastScanResult: (summary: ScanSummary | null) => void;
  dismissScanResult: () => void;
}

const PantryContext = createContext<PantryContextValue | undefined>(undefined);

const RATE_LIMIT_STORAGE_KEY = 'wtc_rate_limited_models_session';

export const PantryProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [pantryIngredients, setPantryIngredients] = useState<Ingredient[]>([]);
  const [allIngredients, setAllIngredients] = useState<Ingredient[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [activeAIProvider, setActiveAIProvider] = useState<AIProvider>('gemini');
  const [activeModel, setActiveModel] = useState<string>('gemini-3.5-flash-lite');
  const [availableModels, setAvailableModels] = useState<Array<{ id: string; displayName?: string; name?: string; description?: string }>>([]);
  const [rateLimitedModels, setRateLimitedModels] = useState<string[]>(() => {
    try {
      const stored = sessionStorage.getItem(RATE_LIMIT_STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [aiProvidersInfo, setAIProvidersInfo] = useState<AIProvidersResponse | null>(null);
  const [isScannerOpen, setIsScannerOpen] = useState<boolean>(false);
  const [lastScanResult, setLastScanResult] = useState<ScanSummary | null>(null);

  const openScanner = useCallback(() => setIsScannerOpen(true), []);
  const closeScanner = useCallback(() => setIsScannerOpen(false), []);
  const dismissScanResult = useCallback(() => setLastScanResult(null), []);

  const { isAuthenticated } = useAuth();
  const { success, error, info } = useToast();

  // Load all system ingredients & AI providers info
  useEffect(() => {
    const initData = async () => {
      try {
        const [ings, providers, modelsData] = await Promise.all([
          recipeApi.getAllIngredients(),
          aiApi.getProviders().catch(() => null),
          aiApi.getModels().catch(() => null),
        ]);
        setAllIngredients(ings);
        if (providers) {
          setAIProvidersInfo(providers);
          if (providers.default_provider) {
            setActiveAIProvider(providers.default_provider);
          }
        }
        if (modelsData) {
          const rawModels = (modelsData.models || (modelsData as any).available_models || []) as Array<{ id: string; displayName?: string; name?: string; description?: string }>;
          if (rawModels.length > 0) {
            setAvailableModels(rawModels);
          }
          if (modelsData.current_model) {
            // Check if current_model is rate limited
            const stored = sessionStorage.getItem(RATE_LIMIT_STORAGE_KEY);
            const blocked: string[] = stored ? JSON.parse(stored) : [];
            if (!blocked.includes(modelsData.current_model)) {
              setActiveModel(modelsData.current_model);
            } else {
              // Find first non-blocked model
              const nextModel = rawModels.find((m) => !blocked.includes(m.id));
              if (nextModel) {
                setActiveModel(nextModel.id);
              }
            }
          }
        }
      } catch (err) {
        console.error('Failed to load initial ingredients:', err);
      }
    };
    initData();
  }, []);

  // Mark model as rate-limited and auto-fallback to next available model
  const markModelRateLimited = useCallback(
    (modelId: string) => {
      if (!modelId) return;
      setRateLimitedModels((prev) => {
        if (prev.includes(modelId)) return prev;
        const updated = [...prev, modelId];
        try {
          sessionStorage.setItem(RATE_LIMIT_STORAGE_KEY, JSON.stringify(updated));
        } catch {
          // Ignore storage errors
        }

        // If the rate-limited model was active, find next alternative
        setActiveModel((currentActive) => {
          if (currentActive === modelId) {
            const fallbackCandidate = availableModels.find((m) => !updated.includes(m.id));
            if (fallbackCandidate) {
              info(
                `Model '${modelId}' reached usage quota. Automatically switched to '${fallbackCandidate.displayName || fallbackCandidate.id}' ⚡`,
                'AI Quota Limit Handled'
              );
              return fallbackCandidate.id;
            }
          }
          return currentActive;
        });

        return updated;
      });
    },
    [availableModels, info]
  );

  const handleRateLimitedModels = useCallback(
    (models: string[]) => {
      if (models && Array.isArray(models)) {
        models.forEach((m) => markModelRateLimited(m));
      }
    },
    [markModelRateLimited]
  );

  // Refresh user pantry
  const refreshPantry = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await pantryApi.getPantry();
      setPantryIngredients(data.ingredients || []);
    } catch (err) {
      setPantryIngredients([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshPantry();
  }, [isAuthenticated, refreshPantry]);

  // Derived available ingredients (system ingredients not in user pantry)
  const availableIngredients = useMemo(
    () => allIngredients.filter((allIng) => !pantryIngredients.some((pIng) => pIng.id === allIng.id)),
    [allIngredients, pantryIngredients]
  );

  const isInPantry = useCallback(
    (ingredientId: number) => pantryIngredients.some((i) => i.id === ingredientId),
    [pantryIngredients]
  );

  const addIngredient = useCallback(
    async (ingredient: Ingredient | number | string) => {
      try {
        let payload: { ingredient_id?: number; name?: string } = {};
        let ingredientName = '';

        if (typeof ingredient === 'number') {
          payload.ingredient_id = ingredient;
          const found = allIngredients.find((i) => i.id === ingredient);
          ingredientName = found ? found.name : 'Ingredient';
        } else if (typeof ingredient === 'string') {
          payload.name = ingredient;
          ingredientName = ingredient;
        } else {
          payload.ingredient_id = ingredient.id;
          ingredientName = ingredient.name;
        }

        const res = await pantryApi.addIngredient(payload);
        setPantryIngredients(res.pantry.ingredients);
        success(`Added ${ingredientName} to your pantry!`, 'Pantry Updated 🧺');
      } catch (err: any) {
        error(err.message || 'Failed to add ingredient.', 'Error');
      }
    },
    [allIngredients, success, error]
  );

  const addMultipleIngredients = useCallback(
    async (ids: number[]) => {
      try {
        const res = await pantryApi.addIngredient({ ingredient_ids: ids });
        setPantryIngredients(res.pantry.ingredients);
        success(`Added ${ids.length} ingredients to your pantry!`, 'Pantry Stocked 🍳');
      } catch (err: any) {
        error(err.message || 'Failed to add ingredients.', 'Error');
      }
    },
    [success, error]
  );

  const removeIngredient = useCallback(
    async (ingredientId: number) => {
      try {
        const ingToRemove = pantryIngredients.find((i) => i.id === ingredientId);
        const res = await pantryApi.removeIngredient(ingredientId);
        setPantryIngredients(res.pantry.ingredients);
        info(`Removed ${ingToRemove?.name || 'ingredient'} from pantry.`, 'Pantry Updated');
      } catch (err: any) {
        error(err.message || 'Failed to remove ingredient.', 'Error');
      }
    },
    [pantryIngredients, info, error]
  );

  const clearPantry = useCallback(async () => {
    try {
      const res = await pantryApi.clearPantry();
      setPantryIngredients(res.pantry.ingredients || []);
      info('Pantry has been cleared.', 'Pantry Reset');
    } catch (err: any) {
      error(err.message || 'Failed to clear pantry.', 'Error');
    }
  }, [info, error]);

  // Stable context identity — pantry consumers only re-render on real changes.
  const value = useMemo<PantryContextValue>(
    () => ({
      pantryIngredients,
      availableIngredients,
      allIngredients,
      isLoading,
      activeAIProvider,
      activeModel,
      availableModels,
      rateLimitedModels,
      aiProvidersInfo,
      setActiveAIProvider,
      setActiveModel,
      markModelRateLimited,
      handleRateLimitedModels,
      addIngredient,
      addMultipleIngredients,
      removeIngredient,
      clearPantry,
      isInPantry,
      refreshPantry,
      isScannerOpen,
      openScanner,
      closeScanner,
      lastScanResult,
      setLastScanResult,
      dismissScanResult,
    }),
    [
      pantryIngredients,
      availableIngredients,
      allIngredients,
      isLoading,
      activeAIProvider,
      activeModel,
      availableModels,
      rateLimitedModels,
      aiProvidersInfo,
      markModelRateLimited,
      handleRateLimitedModels,
      addIngredient,
      addMultipleIngredients,
      removeIngredient,
      clearPantry,
      isInPantry,
      refreshPantry,
      isScannerOpen,
      openScanner,
      closeScanner,
      lastScanResult,
      dismissScanResult,
    ]
  );

  return <PantryContext.Provider value={value}>{children}</PantryContext.Provider>;
};

export const usePantry = (): PantryContextValue => {
  const context = useContext(PantryContext);
  if (!context) {
    throw new Error('usePantry must be used within a PantryProvider');
  }
  return context;
};
