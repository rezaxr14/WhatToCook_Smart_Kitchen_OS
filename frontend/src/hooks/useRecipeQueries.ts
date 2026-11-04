import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { recipeApi } from '../api/recipeApi';
import { CAN_COOK_QUERY_KEY } from './usePantryQueries';

export const RECIPES_QUERY_KEY = ['recipes'] as const;

export const useRecipesQuery = () => {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || 'en';
  return useQuery({
    // `display_*` fields depend on Accept-Language, so the language is part
    // of the cache key; a language switch must refetch.
    queryKey: [...RECIPES_QUERY_KEY, language],
    queryFn: () => recipeApi.getAllRecipes(),
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

export const useCanCookQuery = () => {
  const { i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || 'en';
  return useQuery({
    queryKey: [...CAN_COOK_QUERY_KEY, language],
    queryFn: () => recipeApi.getCanCookRecipes(),
    staleTime: 1000 * 30, // 30 seconds
  });
};
