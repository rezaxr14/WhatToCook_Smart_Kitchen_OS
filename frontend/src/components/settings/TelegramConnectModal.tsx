import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, X, Check, Copy, ExternalLink, Bot, Sparkles, Smartphone, Globe } from 'lucide-react';

interface TelegramConnectModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const TelegramConnectModal: React.FC<TelegramConnectModalProps> = ({ isOpen, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [linkData, setLinkData] = useState<{
    auth_token: string;
    is_connected: boolean;
    telegram_username?: string;
    bot_username?: string;
    connect_url: string;
    direct_tg_url?: string;
    web_tg_url?: string;
  } | null>(null);

  useEffect(() => {
    if (isOpen) {
      fetchTelegramLink();
    }
  }, [isOpen]);

  // Handle ESC key to dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const fetchTelegramLink = async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/telegram/link/', {
        headers: {
          'Content-Type': 'application/json',
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        setLinkData(data);
      }
    } catch (e) {
      console.error('Failed to get Telegram link:', e);
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleCopy = () => {
    if (linkData?.connect_url) {
      navigator.clipboard.writeText(linkData.connect_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const openTelegramDirect = () => {
    if (!linkData) return;
    window.open(linkData.direct_tg_url || linkData.connect_url, '_blank');
  };

  return createPortal(
    <div
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      className="fixed inset-0 z-9999 flex items-center justify-center p-4 bg-stone-950/75 backdrop-blur-md overflow-y-auto"
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="relative w-full max-w-md bg-white rounded-3xl border border-stone-200 shadow-2xl overflow-hidden my-auto"
      >
        {/* Header */}
        <div className="bg-linear-to-r/srgb from-sky-600 via-sky-500 to-sky-700 p-5 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-white/20 border border-white/30 flex items-center justify-center text-white shadow-inner">
              <Bot className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-extrabold text-base text-white">Telegram AI Chef Bot</h3>
              <p className="text-sky-100 text-xs mt-0.5">
                Cook and manage your pantry straight from Telegram!
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-black/20 hover:bg-black/40 text-white flex items-center justify-center transition-all cursor-pointer"
            aria-label="Close modal"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {/* Status Indicator */}
          {linkData?.is_connected ? (
            <div className="p-4 rounded-2xl bg-emerald-50 border border-emerald-200 flex items-center gap-3">
              <div className="w-9 h-9 rounded-full bg-emerald-500 text-white flex items-center justify-center">
                <Check className="w-5 h-5" />
              </div>
              <div>
                <div className="font-extrabold text-xs text-emerald-800">Connected to Telegram!</div>
                <div className="text-xs text-emerald-600">
                  Linked as @{linkData.telegram_username || 'Chef'}
                </div>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Step by step instructions */}
              <div className="p-3.5 bg-sky-50/60 border border-sky-100 rounded-2xl space-y-2">
                <div className="text-[11px] font-extrabold text-sky-900 uppercase tracking-wider">
                  How to Connect in 2 Steps:
                </div>
                <ol className="text-xs text-stone-700 space-y-1.5 list-decimal list-inside leading-relaxed">
                  <li>Tap <strong>Launch in Telegram</strong> below to open the official bot.</li>
                  <li>Click <strong>Start</strong> in Telegram to link your pantry automatically!</li>
                </ol>
              </div>

              {linkData && (
                <div className="space-y-2.5">
                  <div className="grid grid-cols-2 gap-2">
                    <a
                      href={linkData.direct_tg_url || linkData.connect_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="py-3 px-3 bg-sky-500 hover:bg-sky-600 text-white font-extrabold text-xs rounded-2xl flex items-center justify-center gap-2 transition-all shadow-md shadow-sky-500/25"
                    >
                      <Smartphone className="w-4 h-4" />
                      <span>Launch App</span>
                    </a>

                    <a
                      href={linkData.connect_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="py-3 px-3 bg-stone-800 hover:bg-stone-900 text-white font-extrabold text-xs rounded-2xl flex items-center justify-center gap-2 transition-all shadow-md"
                    >
                      <Globe className="w-4 h-4" />
                      <span>Web Telegram</span>
                    </a>
                  </div>

                  <div className="flex items-center gap-2 pt-1">
                    <input
                      type="text"
                      readOnly
                      value={linkData.connect_url}
                      className="flex-1 px-3 py-2 bg-stone-50 border border-stone-200 rounded-xl text-xs text-stone-500 font-mono select-all"
                    />
                    <button
                      onClick={handleCopy}
                      className="px-3 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 text-xs font-bold rounded-xl flex items-center gap-1 transition-colors cursor-pointer"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Bot Features List */}
          <div className="pt-4 border-t border-stone-100 space-y-2">
            <div className="text-[11px] font-extrabold text-stone-400 uppercase tracking-wider">
              Available Bot Commands
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-100">
                <span className="font-bold text-stone-800 font-mono">/cook</span>
                <p className="text-[10px] text-stone-500 mt-0.5">Instant recipe ideas</p>
              </div>
              <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-100">
                <span className="font-bold text-stone-800 font-mono">/pantry</span>
                <p className="text-[10px] text-stone-500 mt-0.5">View stocked items</p>
              </div>
              <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-100">
                <span className="font-bold text-stone-800 font-mono">/add &lt;item&gt;</span>
                <p className="text-[10px] text-stone-500 mt-0.5">Stock your shelf</p>
              </div>
              <div className="p-2.5 rounded-xl bg-stone-50 border border-stone-100">
                <span className="font-bold text-stone-800 font-mono">/remove &lt;item&gt;</span>
                <p className="text-[10px] text-stone-500 mt-0.5">Delete ingredient</p>
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    </div>,
    document.body
  );
};
