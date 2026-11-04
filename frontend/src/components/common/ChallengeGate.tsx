import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ShieldCheck, X } from 'lucide-react';
import { authApi, ChallengeConfig } from '../../api/authApi';
import { TurnstileWidget } from './TurnstileWidget';
import { registerChallengeHandler } from '../../lib/challenge';

/**
 * Global step-up gate for the adaptive AI challenge.
 *
 * `apiClient` asks this component to verify the visitor after an AI response
 * returns `challenge_required`, then retries the original request once. It is
 * inert when Turnstile is not configured, so local development keeps working.
 */
export const ChallengeGate: React.FC = () => {
  const { t } = useTranslation();
  const [config, setConfig] = useState<ChallengeConfig | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [widgetKey, setWidgetKey] = useState(0);
  const resolverRef = useRef<((ok: boolean) => void) | null>(null);

  useEffect(() => {
    authApi
      .getChallenge()
      .then(setConfig)
      .catch(() => setConfig(null));
  }, []);

  const finish = useCallback((ok: boolean) => {
    resolverRef.current?.(ok);
    resolverRef.current = null;
    setOpen(false);
    setBusy(false);
    setError('');
  }, []);

  useEffect(() => {
    if (!config?.enabled || !config.site_key) return undefined;
    return registerChallengeHandler(
      () =>
        new Promise<boolean>((resolve) => {
          resolverRef.current?.(false); // only one gate at a time
          resolverRef.current = resolve;
          setError('');
          setWidgetKey((key) => key + 1);
          setOpen(true);
        })
    );
  }, [config]);

  const handleToken = async (token: string) => {
    if (!token) return;
    setBusy(true);
    setError('');
    try {
      await authApi.verifyChallenge(token);
      finish(true);
    } catch {
      setError(t('challenge.failed'));
      setWidgetKey((key) => key + 1);
      setBusy(false);
    }
  };

  if (!open || !config?.site_key) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-stone-950/60 backdrop-blur-sm p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="challenge-title"
        className="w-full max-w-sm rounded-3xl bg-white border border-stone-200 shadow-2xl p-6 space-y-4"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
              <ShieldCheck className="w-5 h-5" />
            </span>
            <div>
              <h2 id="challenge-title" className="text-sm font-extrabold text-stone-900">
                {t('challenge.title')}
              </h2>
              <p className="text-[11px] text-stone-500">
                {t('challenge.body', { every: config.every_n })}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => finish(false)}
            aria-label={t('challenge.cancel')}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-900 hover:bg-stone-100 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex justify-center">
          <TurnstileWidget
            siteKey={config.site_key}
            action={config.action || 'ai_gate'}
            resetKey={widgetKey}
            onToken={handleToken}
            onExpire={() => setError(t('challenge.expired'))}
          />
        </div>

        {busy && !error && (
          <p className="text-center text-[11px] text-stone-500">{t('challenge.verifying')}</p>
        )}
        {error && (
          <p className="text-center text-[11px] font-semibold text-rose-600">{error}</p>
        )}

        <button
          type="button"
          onClick={() => finish(false)}
          className="w-full py-2 rounded-xl border border-stone-200 text-xs font-bold text-stone-600 hover:bg-stone-50 cursor-pointer"
        >
          {t('challenge.cancel')}
        </button>
      </div>
    </div>
  );
};
