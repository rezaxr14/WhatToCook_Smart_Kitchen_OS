import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { pantryApi } from '../api/pantryApi';
import { Ingredient } from '../types/ingredient';

export const PANTRY_QUERY_KEY = ['pantry'] as const;
export const CAN_COOK_QUERY_KEY = ['canCook'] as const;

export const usePantryQuery = () => {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || 'en';
  return useQuery({
    queryKey: [...PANTRY_QUERY_KEY, language],
    queryFn: async () => {
      const response = await pantryApi.getPantry();
      return response.ingredients;
    },
    staleTime: 1000 * 60 * 2,
  });
};

export const useAddPantryMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { id?: number; name?: string }) => {
      if (payload.id) {
        return pantryApi.addIngredient({ ingredient_id: payload.id });
      } else if (payload.name) {
        return pantryApi.addIngredient({ name: payload.name });
      }
      throw new Error('Either id or name must be provided');
    },
    onMutate: async (newIngredient) => {
      await queryClient.cancelQueries({ queryKey: PANTRY_QUERY_KEY });
      const previousPantry = queryClient.getQueryData<Ingredient[]>(PANTRY_QUERY_KEY) || [];

      // Optimistically add to list
      const optimisticItem: Ingredient = {
        id: newIngredient.id || Date.now(),
        name: newIngredient.name || 'New Item',
        category: 'Produce',
        calories_per_100g: 50,
      };

      if (!previousPantry.some((i) => (newIngredient.id && i.id === newIngredient.id) || (newIngredient.name && i.name.toLowerCase() === newIngredient.name.toLowerCase()))) {
        queryClient.setQueryData<Ingredient[]>(PANTRY_QUERY_KEY, [...previousPantry, optimisticItem]);
      }

      return { previousPantry };
    },
    onError: (_err, _newIngredient, context) => {
      if (context?.previousPantry) {
        queryClient.setQueryData(PANTRY_QUERY_KEY, context.previousPantry);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PANTRY_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: CAN_COOK_QUERY_KEY });
    },
  });
};

export const useRemovePantryMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (ingredientId: number) => {
      return pantryApi.removeIngredient(ingredientId);
    },
    onMutate: async (ingredientId) => {
      await queryClient.cancelQueries({ queryKey: PANTRY_QUERY_KEY });
      const previousPantry = queryClient.getQueryData<Ingredient[]>(PANTRY_QUERY_KEY) || [];

      // Optimistically remove from list
      queryClient.setQueryData<Ingredient[]>(
        PANTRY_QUERY_KEY,
        previousPantry.filter((i) => i.id !== ingredientId)
      );

      return { previousPantry };
    },
    onError: (_err, _id, context) => {
      if (context?.previousPantry) {
        queryClient.setQueryData(PANTRY_QUERY_KEY, context.previousPantry);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PANTRY_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: CAN_COOK_QUERY_KEY });
    },
  });
};

export const useClearPantryMutation = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      return pantryApi.clearPantry();
    },
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: PANTRY_QUERY_KEY });
      const previousPantry = queryClient.getQueryData<Ingredient[]>(PANTRY_QUERY_KEY) || [];
      queryClient.setQueryData<Ingredient[]>(PANTRY_QUERY_KEY, []);
      return { previousPantry };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousPantry) {
        queryClient.setQueryData(PANTRY_QUERY_KEY, context.previousPantry);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: PANTRY_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: CAN_COOK_QUERY_KEY });
    },
  });
};
