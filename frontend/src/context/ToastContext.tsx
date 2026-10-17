import React, { createContext, useContext, useState, useCallback, useMemo, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, Info, Sparkles, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'ai';

export interface ToastItem {
  id: string;
  message: string;
  type: ToastType;
  title?: string;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType, title?: string) => void;
  success: (message: string, title?: string) => void;
  error: (message: string, title?: string) => void;
  info: (message: string, title?: string) => void;
  aiToast: (message: string, title?: string) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastType = 'info', title?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, message, type, title }]);

    setTimeout(() => {
      removeToast(id);
    }, 4000);
  }, [removeToast]);

  const success = useCallback((msg: string, title?: string) => showToast(msg, 'success', title), [showToast]);
  const error = useCallback((msg: string, title?: string) => showToast(msg, 'error', title), [showToast]);
  const info = useCallback((msg: string, title?: string) => showToast(msg, 'info', title), [showToast]);
  const aiToast = useCallback((msg: string, title?: string) => showToast(msg, 'ai', title || 'AI Chef'), [showToast]);

  // Stable context identity — toast helpers never invalidate consumers.
  const value = useMemo<ToastContextValue>(
    () => ({ showToast, success, error, info, aiToast }),
    [showToast, success, error, info, aiToast]
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, y: 20, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.9 }}
              transition={{ duration: 0.2 }}
              className={`pointer-events-auto p-4 rounded-2xl shadow-xl backdrop-blur-lg border flex items-start gap-3 text-sm ${
 toast.type === 'success'
 ? 'bg-white/95 border-emerald-200 text-emerald-950 shadow-emerald-500/10'
 : toast.type === 'error'
 ? 'bg-white/95 border-rose-200 text-rose-950 shadow-rose-500/10'
 : toast.type === 'ai'
 ? 'bg-linear-to-r/srgb from-orange-500/95 to-amber-500/95 text-white border-orange-400 shadow-orange-500/20'
 : 'bg-white/95 border-stone-200 text-stone-900 shadow-stone-500/10'
 }`}
            >
              <div className="mt-0.5 shrink-0">
                {toast.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                {toast.type === 'error' && <AlertCircle className="w-5 h-5 text-rose-600" />}
                {toast.type === 'ai'&& <Sparkles className="w-5 h-5 text-amber-200 animate-spin" style={{ animationDuration:'4s' }} />}
                {toast.type === 'info' && <Info className="w-5 h-5 text-brand-600" />}
              </div>
              <div className="flex-1">
                {toast.title && <div className="font-semibold mb-0.5">{toast.title}</div>}
                <div className={toast.type === 'ai' ? 'text-white/90' : 'text-stone-600'}>{toast.message}</div>
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="opacity-70 hover:opacity-100 transition-opacity p-0.5"
              >
                <X className="w-4 h-4" />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
