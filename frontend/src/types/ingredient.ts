export interface Ingredient {
  id: number;
  name: string;
  display_name?: string;
  calories_per_100g: number | null;
  category: string;
  image_url?: string;
  image_fallback?: string | null;
}

export interface RecipeIngredient {
  id: number;
  ingredient: Ingredient;
  quantity: string;
  unit: string;
}

export interface ScannedIngredient {
  name: string;
  display_name?: string;
  category: string;
  confidence: number;
  estimated_quantity?: string | null;
}

export interface ScanFridgeResponse {
  status: string;
  detected_count: number;
  detected_ingredients: ScannedIngredient[];
  auto_added: boolean;
  added_ingredients: string[];
  pantry?: any;
}
