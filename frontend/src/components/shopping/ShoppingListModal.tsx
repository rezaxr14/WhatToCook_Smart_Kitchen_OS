import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShoppingCart,
  X,
  Plus,
  Trash2,
  CheckCircle2,
  Circle,
  Share2,
  MessageSquare,
  Copy,
  Printer,
  Sparkles,
  Send,
  Check,
} from 'lucide-react';
import { useShoppingList } from '../../context/ShoppingListContext';

interface ShoppingListModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const ShoppingListModal: React.FC<ShoppingListModalProps> = ({ isOpen, onClose }) => {
  const {
    items,
    addItem,
    toggleItem,
    removeItem,
    clearCompleted,
    clearAll,
    exportToWhatsApp,
    exportToTelegram,
    copyToClipboard,
    printList,
  } = useShoppingList();

  const [newItemName, setNewItemName] = useState('');
  const [newItemQuantity, setNewItemQuantity] = useState('');
  const [copied, setCopied] = useState(false);

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

  if (!isOpen) return null;

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newItemName.trim()) return;
    addItem(newItemName, 'General', newItemQuantity || undefined);
    setNewItemName('');
    setNewItemQuantity('');
  };

  const handleCopy = async () => {
    const success = await copyToClipboard();
    if (success) {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const checkedCount = items.filter((i) => i.checked).length;
  const progress = items.length > 0 ? (checkedCount / items.length) * 100 : 0;

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
        className="relative w-full max-w-xl bg-white rounded-3xl border border-stone-200 shadow-2xl overflow-hidden my-auto"
      >
        {/* Header */}
        <div className="bg-linear-to-r/srgb from-stone-900 via-stone-850 to-stone-950 p-6 text-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-2xl bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <ShoppingCart className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-extrabold text-lg text-white">Smart Grocery List</h3>
                <span className="bg-brand-500 text-white font-black text-[10px] px-2 py-0.5 rounded-full">
                  {items.length} {items.length === 1 ? 'item' : 'items'}
                </span>
              </div>
              <p className="text-stone-400 text-xs mt-0.5">
                Export to WhatsApp & Telegram or print your kitchen shopping list.
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-stone-300 hover:text-white flex items-center justify-center transition-colors cursor-pointer"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Progress Bar */}
        {items.length > 0 && (
          <div className="h-1.5 w-full bg-stone-100">
            <div
              className="h-full bg-emerald-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        )}

        <div className="p-6 space-y-6">
          {/* Quick Add Input */}
          <form onSubmit={handleAdd} className="flex gap-2">
            <input
              type="text"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              placeholder="Add item (e.g. Olive Oil, Garlic, Parmesan)..."
              className="flex-1 px-4 py-2.5 rounded-2xl border border-stone-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500 text-sm"
            />
            <input
              type="text"
              value={newItemQuantity}
              onChange={(e) => setNewItemQuantity(e.target.value)}
              placeholder="Qty (e.g. 250ml)"
              className="w-28 px-3 py-2.5 rounded-2xl border border-stone-200 focus:outline-hidden focus:ring-2 focus:ring-brand-500 text-sm hidden sm:block"
            />
            <button
              type="submit"
              className="px-4 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-2xl font-bold text-sm flex items-center gap-1.5 shadow-xs transition-all cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden sm:inline">Add</span>
            </button>
          </form>

          {/* Items List */}
          {items.length === 0 ? (
            <div className="py-12 text-center text-stone-400 space-y-2">
              <div className="w-12 h-12 rounded-2xl bg-stone-100 flex items-center justify-center mx-auto text-stone-300">
                <ShoppingCart className="w-6 h-6" />
              </div>
              <p className="text-sm font-semibold text-stone-600">Your grocery list is empty!</p>
              <p className="text-xs text-stone-400">
                Add missing ingredients directly from any recipe with 1-click.
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
              {items.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center justify-between p-3 rounded-2xl border transition-all ${
 item.checked
 ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900 opacity-60'
 : 'bg-stone-50 border-stone-200 text-stone-800'
 }`}
                >
                  <button
                    type="button"
                    onClick={() => toggleItem(item.id)}
                    className="flex items-center gap-3 min-w-0 flex-1 text-left cursor-pointer"
                  >
                    {item.checked ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0" />
                    ) : (
                      <Circle className="w-5 h-5 text-stone-300 shrink-0 hover:text-stone-400" />
                    )}
                    <div className="min-w-0">
                      <p
                        className={`text-sm font-bold truncate ${
 item.checked ? 'line-through text-stone-500' : 'text-stone-900'
 }`}
                      >
                        {item.name}
                      </p>
                      {item.addedFrom && (
                        <p className="text-[10px] text-stone-400 truncate">From: {item.addedFrom}</p>
                      )}
                    </div>
                  </button>

                  <div className="flex items-center gap-3">
                    {item.quantity && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-lg bg-stone-200/70 text-stone-700">
                        {item.quantity}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="text-stone-300 hover:text-rose-500 p-1 transition-colors cursor-pointer"
                      aria-label="Remove item"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Action Export Buttons */}
          {items.length > 0 && (
            <div className="space-y-4 pt-4 border-t border-stone-100">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                <button
                  onClick={exportToWhatsApp}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold text-xs border border-emerald-200/80 transition-all cursor-pointer"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>WhatsApp</span>
                </button>

                <button
                  onClick={exportToTelegram}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl bg-sky-50 hover:bg-sky-100 text-sky-700 font-bold text-xs border border-sky-200/80 transition-all cursor-pointer"
                >
                  <Send className="w-4 h-4" />
                  <span>Telegram</span>
                </button>

                <button
                  onClick={handleCopy}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-700 font-bold text-xs border border-stone-200 transition-all cursor-pointer"
                >
                  {copied ? <Check className="w-4 h-4 text-emerald-600" /> : <Copy className="w-4 h-4" />}
                  <span>{copied ? 'Copied!' : 'Copy Text'}</span>
                </button>

                <button
                  onClick={printList}
                  className="flex items-center justify-center gap-1.5 p-2.5 rounded-xl bg-stone-100 hover:bg-stone-200 text-stone-700 font-bold text-xs border border-stone-200 transition-all cursor-pointer"
                >
                  <Printer className="w-4 h-4" />
                  <span>Print</span>
                </button>
              </div>

              {/* Bottom Quick Controls */}
              <div className="flex items-center justify-between text-xs text-stone-400 font-semibold px-1">
                <button
                  onClick={clearCompleted}
                  disabled={checkedCount === 0}
                  className="hover:text-stone-600 disabled:opacity-30 transition-colors cursor-pointer"
                >
                  Clear {checkedCount} Completed
                </button>
                <button
                  onClick={clearAll}
                  className="hover:text-rose-500 transition-colors cursor-pointer"
                >
                  Clear Entire List
                </button>
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </div>,
    document.body
  );
};
