import React from 'react';
import { ShoppingCart, Send, Globe } from 'lucide-react';
import { useShoppingList } from '../../context/ShoppingListContext';
import { useLanguageModal } from './LanguageModal';
import { useTranslation } from 'react-i18next';

export const QuickActionsWidget: React.FC = () => {
  const { items, openShoppingModal, openTelegramModal } = useShoppingList();
  const { openModal: openLanguageModal } = useLanguageModal();
  const { t } = useTranslation();
  const uncheckedCount = items.filter((i) => !i.checked).length;

  return (
    <>
      {/* Language — opposite corner from the utility actions */}
      <aside aria-label="Language" className="fixed bottom-4 sm:bottom-6 inset-s-4 sm:inset-s-6 z-30" dir="ltr">
        <button
          type="button"
          onClick={openLanguageModal}
          className="group flex items-center gap-2 px-3.5 py-2.5 rounded-full bg-white/95 hover:bg-white text-stone-800 border border-stone-200/90 shadow-lg hover:shadow-xl hover:border-sage-400 transition-all duration-300 backdrop-blur-md cursor-pointer hover:scale-105"
          title={t('quickActions.language')}
        >
          <div className="w-7 h-7 rounded-full bg-sage-50 text-sage-600 flex items-center justify-center">
            <Globe className="w-4 h-4" />
          </div>
          <span className="text-xs font-extrabold text-stone-800 hidden md:inline">
            {t('quickActions.language')}
          </span>
        </button>
      </aside>

      {/* Grocery & Telegram — right corner */}
      <aside
        aria-label="Quick Actions"
        className="fixed bottom-4 sm:bottom-6 inset-e-4 sm:inset-e-6 z-30 flex items-center gap-2.5"
        dir="ltr"
      >
        {/* Quick Grocery List Trigger */}
        <button
          type="button"
          onClick={openShoppingModal}
          className="group flex items-center gap-2 px-3.5 py-2.5 rounded-full bg-white/95 hover:bg-white text-stone-800 border border-stone-200/90 shadow-lg hover:shadow-xl hover:border-brand-400 transition-all duration-300 backdrop-blur-md cursor-pointer hover:scale-105"
          title={t('quickActions.grocery')}
        >
          <div className="w-7 h-7 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center">
            <ShoppingCart className="w-4 h-4" />
          </div>
          <span className="text-xs font-extrabold text-stone-800 hidden sm:inline">
            {t('quickActions.grocery')}
          </span>
          {uncheckedCount > 0 && (
            <span className="bg-brand-500 text-white font-black text-[10px] px-2 py-0.5 rounded-full">
              {uncheckedCount}
            </span>
          )}
        </button>

        {/* Quick Telegram Bot Trigger */}
        <button
          type="button"
          onClick={openTelegramModal}
          className="group flex items-center gap-2 px-3.5 py-2.5 rounded-full bg-sky-500 hover:bg-sky-600 text-white shadow-lg shadow-sky-500/25 hover:shadow-xl hover:shadow-sky-500/40 transition-all duration-300 cursor-pointer hover:scale-105"
          title={t('quickActions.telegram')}
        >
          <Send className="w-4 h-4" />
          <span className="text-xs font-extrabold hidden sm:inline">
            {t('quickActions.telegram')}
          </span>
        </button>
      </aside>
    </>
  );
};
