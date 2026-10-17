import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { SUPPORTED_LANGUAGES, LANGUAGE_STORAGE_KEY } from '../../i18n';
import { StyledButton } from './StyledButton';

interface LanguageContextValue {
  isModalOpen: boolean;
  openModal: () => void;
  closeModal: () => void;
}

const LanguageContext = createContext<LanguageContextValue | undefined>(undefined);

export const LanguageProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const openModal = useCallback(() => setIsModalOpen(true), []);
  const closeModal = useCallback(() => setIsModalOpen(false), []);

  return (
    <LanguageContext.Provider value={{ isModalOpen, openModal, closeModal }}>
      {children}
      <FirstVisitGate onNeedSelection={() => setIsModalOpen(true)} />
      <LanguageModal isOpen={isModalOpen} onClose={closeModal} showClose={isModalOpen && !!localStorage.getItem(LANGUAGE_STORAGE_KEY)} />
    </LanguageContext.Provider>
  );
};

/**
 * Shows the language picker the very first time someone lands on the site.
 * Runs once; afterwards the choice lives in localStorage (via i18next detector).
 */
const FirstVisitGate: React.FC<{ onNeedSelection: () => void }> = ({ onNeedSelection }) => {
  const cbRef = React.useRef(onNeedSelection);
  cbRef.current = onNeedSelection;
  const openedRef = React.useRef(false);

  const fire = React.useCallback(() => {
    if (openedRef.current) return; // already shown — never nag after a dismissal
    let chosen = false;
    try {
      chosen = !!localStorage.getItem(LANGUAGE_STORAGE_KEY);
    } catch {
      chosen = true; // storage unavailable — skip gate
    }
    if (chosen) return;
    openedRef.current = true;
    cbRef.current();
  }, []);

  React.useEffect(() => {
    // First paint can be stalled for several seconds while the heavy 3D
    // landing scene initialises (software WebGL, low-end GPUs, dev cold
    // compile), which blocks the main thread and pushes setTimeout
    // callbacks far past their delay. Fire staggered attempts so the
    // picker reliably appears the moment the thread frees up.
    const t1 = setTimeout(fire, 600);
    const t2 = setTimeout(fire, 6000);
    const t3 = setTimeout(fire, 15000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [fire]);
  return null;
};

export const useLanguageModal = (): LanguageContextValue => {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error('useLanguageModal must be used within LanguageProvider');
  return ctx;
};

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  showClose?: boolean;
}

export const LanguageModal: React.FC<ModalProps> = ({ isOpen, onClose, showClose = true }) => {
  const { i18n, t } = useTranslation();
  const current = i18n.language?.split('-')[0] || 'en';

  React.useEffect(() => {
    if (!isOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isOpen, onClose]);

  const select = (code: string) => {
    i18n.changeLanguage(code);
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, code);
    } catch {
      /* ignore */
    }
    // Small delay so users see their selection before the sheet closes.
    setTimeout(onClose, 180);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="fixed inset-0 z-70 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-label={t('language.title')}
            className="relative w-full max-w-lg rounded-3xl bg-white shadow-2xl border border-stone-200 p-6 sm:p-8"
            initial={{ scale: 0.92, y: 24, opacity: 0 }}
            animate={{ scale: 1, y: 0, opacity: 1 }}
            exit={{ scale: 0.95, y: 12, opacity: 0 }}
            transition={{ type: 'spring', damping: 24, stiffness: 320 }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="text-center space-y-1.5 mb-6">
              <div className="mx-auto w-14 h-14 rounded-2xl bg-linear-to-tr/srgb from-brand-500 to-sage-500 flex items-center justify-center text-white mb-3">
                <Globe className="w-7 h-7" />
              </div>
              <h2 className="text-xl sm:text-2xl font-black text-stone-900 tracking-tight">
                {t('language.title')}
              </h2>
              <p className="text-sm text-stone-500">{t('language.subtitle')}</p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5" dir="ltr">
              {SUPPORTED_LANGUAGES.map((lang) => {
                const selected = current === lang.code;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    onClick={() => select(lang.code)}
                    aria-pressed={selected}
                    className={`flex items-center gap-2.5 p-3 rounded-2xl border text-start transition-all cursor-pointer ${
 selected
 ? 'border-brand-500 bg-brand-50 ring-2 ring-brand-200'
 : 'border-stone-200 hover:border-brand-300 hover:bg-stone-50'
 }`}
                  >
                    <span className="text-2xl leading-none">{lang.flag}</span>
                    <span className="min-w-0">
                      <span className="block font-bold text-sm text-stone-900 truncate">
                        {lang.nativeName}
                      </span>
                      <span className="block text-[11px] text-stone-400">{lang.name}</span>
                    </span>
                    {selected && <Check className="w-4 h-4 ms-auto text-brand-600 shrink-0" />}
                  </button>
                );
              })}
            </div>

            {showClose && (
              <div className="mt-6 flex justify-center">
                <StyledButton $variant="ghost" $size="sm" onClick={onClose}>
                  {t('common.close')}
                </StyledButton>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
