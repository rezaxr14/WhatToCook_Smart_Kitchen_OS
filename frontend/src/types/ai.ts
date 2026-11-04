export type AIProvider = 'gemini' | 'lmstudio' | 'supabase_gateway';

export interface AISuggestedDish {
  name: string;
  short_description: string;
  cuisine: string;
  difficulty: 'Easy' | 'Medium' | 'Hard' | string;
  prep_time?: string;
  image_hint?: string;
  image?: string;
  provider?: string;
}

export interface AIRecipeInstruction {
  step: string;
  time_minutes?: number | null;
  chef_tip?: string | null;
}

export interface AIRecipeIngredient {
  name: string;
  amount: string;
  unit: string;
}

export interface AIRecipeDetail {
  name: string;
  description: string;
  cuisine: string;
  difficulty: string;
  time_minutes: number;
  ingredients: AIRecipeIngredient[];
  instructions: (AIRecipeInstruction | string)[];
  nutrition?: {
    calories?: string;
    protein?: string;
    carbs?: string;
    fat?: string;
  };
  image?: string;
  provider?: string;
}

export interface AIProviderInfo {
  id: AIProvider;
  name: string;
  active: boolean;
  online?: boolean;
  badge: string;
  group?: 'cloud' | 'local';
}

export interface AIProviderGroup {
  id: string;
  label: string;
  providers: AIProviderInfo[];
}

export interface AIProvidersResponse {
  default_provider: AIProvider;
  has_gemini: boolean;
  has_gateway?: boolean;
  gateway_configured?: boolean;
  gemini_model: string;
  has_lmstudio: boolean;
  lmstudio_online: boolean;
  lmstudio_model: string;
  lmstudio_error?: string;
  providers: AIProviderInfo[];
  groups?: AIProviderGroup[];
}

export interface AIModelInfo {
  id: string;
  displayName: string;
  description?: string;
  group?: 'cloud' | 'local';
}

export interface AIModelsResponse {
  models: AIModelInfo[];
  current_model: string;
  is_live: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  modelUsed?: string;
}

export interface RecipeChatRequest {
  recipe_name: string;
  ingredients?: any;
  instructions?: any;
  message: string;
  history?: Array<{ role: string; content: string }>;
  provider?: string;
  model?: string;
  language?: string;
}

export interface RecipeChatResponse {
  reply: string;
  model_used: string;
  rate_limited_models?: string[];
  recipe_name: string;
}

