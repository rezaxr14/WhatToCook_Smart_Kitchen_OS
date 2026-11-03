import { useTranslation } from 'react-i18next';
import { getLanguageDir } from '../i18n';

/** Text direction of the active UI language. */
export const useUiDir = (): 'ltr' | 'rtl' => {
  const { i18n } = useTranslation();
  return getLanguageDir(i18n.resolvedLanguage || i18n.language || 'en');
};

/**
 * Direction for a free-text input.
 *
 * Do not use `dir="auto"` alone: an empty `auto` input resolves to LTR, which
 * puts the placeholder on the left in a Persian/Arabic UI. Follow the UI until
 * there is text, then let the browser detect the script the user typed.
 * Email, password, URL and number fields stay explicitly LTR.
 */
export const inputDir = (value: string, uiDir: 'ltr' | 'rtl'): 'ltr' | 'rtl' | 'auto' =>
  value ? 'auto' : uiDir;
