import React, { useState, useEffect, useMemo, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import {
  ShoppingCart,
  X,
  Plus,
  Minus,
  Trash2,
  CheckCircle2,
  Circle,
  MessageSquare,
  Copy,
  Printer,
  Sparkles,
  Send,
  Check,
  Search,
  AlertCircle,
  Tag,
} from 'lucide-react';
import { useShoppingList } from '../../context/ShoppingListContext';
import { usePantry } from '../../context/PantryContext';

interface ShoppingListModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const POPULAR_ITEMS = [
  'Eggs',
  'Milk',
  'Garlic',
  'Onion',
  'Tomato',
  'Butter',
  'Bread',
  'Pasta',
  'Rice',
  'Olive Oil',
];

const UNITS = ['pcs', 'g', 'kg', 'ml', 'l', 'pack', 'bunch', 'can'];

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

  const { allIngredients } = usePantry();

  const [newItemName, setNewItemName] = useState('');
  const [newItemCategory, setNewItemCategory] = useState('General');
  const [amount, setAmount] = useState('1');
  const [unit, setUnit] = useState('pcs');
  const [copied, setCopied] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(0);

  const nameInputRef = useRef<HTMLInputElement | null>(null);

  const suggestions = useMemo(() => {
    const term = newItemName.trim().toLowerCase();
    if (!term) return [];
    return allIngredients
      .filter((ingredient) => ingredient.name.toLowerCase().includes(term))
      .sort((a, b) => {
        const ai = a.name.toLowerCase().indexOf(term);
        const bi = b.name.toLowerCase().indexOf(term);
        if (ai !== bi) return ai - bi;
        return a.name.localeCompare(b.name);
      })
      .slice(0, 8);
  }, [allIngredients, newItemName]);

  useEffect(() => {
    setActiveSuggestion(0);
  }, [newItemName]);

  const newQuantity = `${Math.max(1, Number(amount) || 1)} ${unit}`;

  const isAlreadyOnList = (name: string) =>
    items.some((item) => item.name.toLowerCase() === name.trim().toLowerCase());

  // Handle ESC key to dismiss
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (showSuggestions) {
          setShowSuggestions(false);
          return;
        }
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose, showSuggestions]);

  if (!isOpen) return null;

  const pickSuggestion = (name: string, category: string) => {
    setNewItemName(name);
    setNewItemCategory(category);
    setShowSuggestions(false);
    setAddError(null);
    nameInputRef.current?.focus();
  };

  const handleAdd = (e?: React.FormEvent) => {
    e?.preventDefault();
    const name = newItemName.trim();
    if (!name) return;

    if (isAlreadyOnList(name)) {
      setAddError(`"${name}" is already on your grocery list.`);
      return;
    }

    addItem(name, newItemCategory, newQuantity);
    setNewItemName('');
    setNewItemCategory('General');
    setAmount('1');
    setUnit('pcs');
    setAddError(null);
    setShowSuggestions(false);
    nameInputRef.current?.focus();
  };

  const handleNameKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === 'ArrowDown' && suggestions.length > 0) {
        e.preventDefault();
        setShowSuggestions(true);
      }
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveSuggestion((index) => (index + 1) % suggestions.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveSuggestion((index) => (index - 1 + suggestions.length) % suggestions.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const picked = suggestions[activeSuggestion];
      if (picked) pickSuggestion(picked.name, picked.category);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setShowSuggestions(false);
    }
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
          <form
            onSubmit={handleAdd}
            className="space-y-2.5 rounded-2xl border border-stone-200 bg-stone-50/80 p-3"
          >
            <div className="relative">
              <Search className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone-400" />
              <input
                ref={nameInputRef}
                type="text"
                value={newItemName}
                onChange={(e) => {
                  setNewItemName(e.target.value);
                  setNewItemCategory('General');
                  setAddError(null);
                  setShowSuggestions(true);
                }}
                onFocus={() => setShowSuggestions(true)}
                onBlur={() => window.setTimeout(() => setShowSuggestions(false), 120)}
                onKeyDown={handleNameKeyDown}
                placeholder="Add an item — type to search the catalog..."
                aria-label="Grocery item name"
                autoComplete="off"
                className="w-full rounded-xl border border-stone-200 bg-white py-2.5 ps-9 pe-3 text-sm font-medium focus:outline-hidden focus:ring-2 focus:ring-brand-500"
              />

              {showSuggestions && suggestions.length > 0 && (
                <div className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-2xl border border-stone-200 bg-white p-1 shadow-2xl">
                  {suggestions.map((ingredient, index) => {
                    const already = isAlreadyOnList(ingredient.name);
                    return (
                      <button
                        key={ingredient.id}
                        type="button"
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => pickSuggestion(ingredient.name, ingredient.category)}
                        className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2 text-start transition-colors ${
                          index === activeSuggestion ? 'bg-brand-50' : 'hover:bg-stone-50'
                        }`}
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-sm font-bold text-stone-900">
                            {ingredient.name}
                          </span>
                          <span className="block text-[11px] text-stone-400">
                            {ingredient.category}
                          </span>
                        </span>
                        {already ? (
                          <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                            On list
                          </span>
                        ) : (
                          <Plus className="h-4 w-4 shrink-0 text-brand-500" />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Amount stepper */}
              <div className="flex items-center overflow-hidden rounded-xl border border-stone-200 bg-white">
                <button
                  type="button"
                  aria-label="Decrease quantity"
                  onClick={() =>
                    setAmount((current) => String(Math.max(1, (Number(current) || 1) - 1)))
                  }
                  className="px-2.5 py-2 text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-800 cursor-pointer"
                >
                  <Minus className="h-3.5 w-3.5" />
                </button>
                <input
                  type="text"
                  inputMode="decimal"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
                  aria-label="Quantity"
                  className="w-12 border-x border-stone-100 py-2 text-center text-sm font-extrabold text-stone-900 focus:outline-hidden"
                />
                <button
                  type="button"
                  aria-label="Increase quantity"
                  onClick={() => setAmount((current) => String((Number(current) || 1) + 1))}
                  className="px-2.5 py-2 text-stone-500 transition-colors hover:bg-stone-100 hover:text-stone-800 cursor-pointer"
                >
                  <Plus className="h-3.5 w-3.5" />
                </button>
              </div>

              <select
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                aria-label="Unit"
                className="rounded-xl border border-stone-200 bg-white px-2.5 py-2 text-sm font-bold text-stone-700 focus:outline-hidden focus:ring-2 focus:ring-brand-500 cursor-pointer"
              >
                {UNITS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>

              {newItemCategory !== 'General' && (
                <span className="inline-flex items-center gap-1 rounded-lg bg-stone-200/70 px-2 py-1 text-[11px] font-bold text-stone-600">
                  <Tag className="h-3 w-3" />
                  {newItemCategory}
                </span>
              )}

              <button
                type="submit"
                className="ms-auto inline-flex items-center gap-1.5 rounded-xl bg-brand-500 px-4 py-2 text-sm font-extrabold text-white shadow-xs transition-all hover:bg-brand-600 disabled:opacity-40 cursor-pointer"
                disabled={!newItemName.trim()}
              >
                <Plus className="h-4 w-4" />
                <span>Add</span>
              </button>
            </div>

            {addError && (
              <p className="flex items-center gap-1.5 text-xs font-bold text-rose-600">
                <AlertCircle className="h-3.5 w-3.5" />
                {addError}
              </p>
            )}
          </form>

          {/* Popular picks — one tap fills the item and its quantity controls. */}
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="me-1 inline-flex items-center gap-1 text-[11px] font-black uppercase tracking-wider text-stone-400">
              <Sparkles className="h-3 w-3" />
              Popular
            </span>
            {POPULAR_ITEMS.map((name) => {
              const match = allIngredients.find(
                (ingredient) => ingredient.name.toLowerCase() === name.toLowerCase()
              );
              return (
                <button
                  key={name}
                  type="button"
                  disabled={!match}
                  onClick={() => match && pickSuggestion(match.name, match.category)}
                  className="rounded-full border border-stone-200 bg-white px-2.5 py-1 text-[11px] font-bold text-stone-600 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-40 cursor-pointer"
                >
                  {name}
                </button>
              );
            })}
          </div>

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
            <div className="space-y-2 max-h-72 overflow-y-auto pe-1">
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
                    className="flex items-center gap-3 min-w-0 flex-1 text-start cursor-pointer"
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
                        <p className="text-[10px] text-stone-400 truncate">
                          From: {item.addedFrom}
                        </p>
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
                  {copied ? (
                    <Check className="w-4 h-4 text-emerald-600" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
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
