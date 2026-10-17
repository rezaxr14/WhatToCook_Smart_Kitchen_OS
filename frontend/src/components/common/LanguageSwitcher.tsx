import React, { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Globe, ChevronDown, Check } from 'lucide-react';
import { SUPPORTED_LANGUAGES } from '../../i18n';

export const LanguageSwitcher: React.FC = () => {
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const current = i18n.language?.split('-')[0] || 'en';
  const active = SUPPORTED_LANGUAGES.find((l) => l.code === current) || SUPPORTED_LANGUAGES[0];

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-stone-200 text-xs font-bold border border-white/10 transition-colors cursor-pointer"
      >
        <Globe className="w-3.5 h-3.5" />
        <span>{active.flag}</span>
        <span>{active.nativeName}</span>
        <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <ul
          role="listbox"
          aria-label={t('language.label')}
          dir="ltr"
          className="absolute bottom-full mb-2 inset-e-0 w-48 rounded-2xl bg-stone-900 border border-stone-700 shadow-2xl p-1.5 space-y-0.5 z-50"
        >
          {SUPPORTED_LANGUAGES.map((lang) => {
            const selected = current === lang.code;
            return (
              <li key={lang.code}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => {
                    i18n.changeLanguage(lang.code);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl text-xs transition-colors cursor-pointer ${
 selected ? 'bg-brand-500 text-white font-bold' : 'text-stone-300 hover:bg-stone-800'
 }`}
                >
                  <span className="text-base leading-none">{lang.flag}</span>
                  <span className="font-semibold">{lang.nativeName}</span>
                  <span className={`ms-auto text-[10px] ${selected ? 'text-amber-100' : 'text-stone-500'}`}>
                    {lang.name}
                  </span>
                  {selected && <Check className="w-3 h-3 shrink-0" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
