import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import confetti from 'canvas-confetti';
import { ShoppingListModal } from '../components/shopping/ShoppingListModal';
import { TelegramConnectModal } from '../components/settings/TelegramConnectModal';
import { getCsrfToken } from '../api/client';

export interface ShoppingItem {
  id: string;
  name: string;
  category?: string;
  quantity?: string;
  checked: boolean;
  addedFrom?: string;
}

interface ShoppingListContextType {
  items: ShoppingItem[];
  isShoppingModalOpen: boolean;
  isTelegramModalOpen: boolean;
  openShoppingModal: () => void;
  closeShoppingModal: () => void;
  openTelegramModal: () => void;
  closeTelegramModal: () => void;
  addItem: (name: string, category?: string, quantity?: string, addedFrom?: string) => void;
  addMultipleItems: (newItems: Array<{ name: string; category?: string; quantity?: string; addedFrom?: string }>, autoOpenModal?: boolean) => void;
  toggleItem: (id: string) => void;
  removeItem: (id: string) => void;
  clearCompleted: () => void;
  clearAll: () => void;
  exportToWhatsApp: () => void;
  exportToTelegram: () => void;
  copyToClipboard: () => Promise<boolean>;
  printList: () => void;
}

const ShoppingListContext = createContext<ShoppingListContextType | undefined>(undefined);

const STORAGE_KEY = 'whattocook_shopping_list_v1';

export const ShoppingListProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [items, setItems] = useState<ShoppingItem[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [isShoppingModalOpen, setIsShoppingModalOpen] = useState(false);
  const [isTelegramModalOpen, setIsTelegramModalOpen] = useState(false);

  const openShoppingModal = useCallback(() => setIsShoppingModalOpen(true), []);
  const closeShoppingModal = useCallback(() => setIsShoppingModalOpen(false), []);
  const openTelegramModal = useCallback(() => setIsTelegramModalOpen(true), []);
  const closeTelegramModal = useCallback(() => setIsTelegramModalOpen(false), []);

  // Initial load: Fetch from Database API and merge with local cache
  useEffect(() => {
    const fetchRemoteItems = async () => {
      try {
        // Same-origin cookies identify the owner (account or anonymous session); without them the API has no list for us.
        const res = await fetch('/api/shopping-list/', { credentials: 'same-origin' });
        if (res.ok) {
          const data = await res.json();
          if (Array.isArray(data.items) && data.items.length > 0) {
            setItems((local) => {
              const localMap = new Map(local.map((i) => [i.name.toLowerCase(), i]));
              const merged = [...local];
              for (const r of data.items) {
                if (!localMap.has(r.name.toLowerCase())) {
                  merged.push({
                    id: String(r.id),
                    name: r.name,
                    category: r.category || 'General',
                    quantity: r.quantity || '1 item',
                    checked: Boolean(r.checked),
                    addedFrom: r.added_from,
                  });
                }
              }
              return merged;
            });
          }
        }
      } catch (err) {
        console.warn('Shopping list remote sync unavailable (using local cache):', err);
      }
    };
    fetchRemoteItems();
  }, []);

  // Save to LocalStorage and Sync to Backend Database
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      console.error('Failed to save shopping list to localStorage:', e);
    }

    const timer = setTimeout(async () => {
      try {
        await fetch('/api/shopping-list/sync/', {
          method: 'POST',
          credentials: 'same-origin',
          // Logged-in sessions are CSRF-checked by DRF; without this header the sync was rejected (403) for them.
          headers: { 'Content-Type': 'application/json', ...(getCsrfToken() ? { 'X-CSRFToken': getCsrfToken() as string } : {}) },
          body: JSON.stringify({
            items: items.map((i) => ({
              name: i.name,
              category: i.category,
              quantity: i.quantity,
              checked: i.checked,
              added_from: i.addedFrom,
            })),
          }),
        });
      } catch {
        // Silently preserve locally if server is unreachable
      }
    }, 600);

    return () => clearTimeout(timer);
  }, [items]);

  const addItem = useCallback((name: string, category?: string, quantity?: string, addedFrom?: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;

    setItems((prev) => {
      if (prev.some((item) => item.name.toLowerCase() === trimmed.toLowerCase())) {
        return prev;
      }
      return [
        ...prev,
        {
          id: `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
          name: trimmed,
          category: category || 'General',
          quantity: quantity || '1 item',
          checked: false,
          addedFrom,
        },
      ];
    });
  }, []);

  const addMultipleItems = useCallback(
    (
      newItems: Array<{ name: string; category?: string; quantity?: string; addedFrom?: string }>,
      autoOpenModal: boolean = false
    ) => {
      setItems((prev) => {
        const existingNames = new Set(prev.map((i) => i.name.toLowerCase()));
        const toAdd: ShoppingItem[] = [];

        for (const item of newItems) {
          const trimmed = item.name.trim();
          if (trimmed && !existingNames.has(trimmed.toLowerCase())) {
            existingNames.add(trimmed.toLowerCase());
            toAdd.push({
              id: `${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
              name: trimmed,
              category: item.category || 'General',
              quantity: item.quantity || '1 item',
              checked: false,
              addedFrom: item.addedFrom,
            });
          }
        }

        if (toAdd.length > 0) {
          confetti({ particleCount: 60, spread: 60, origin: { y: 0.7 } });
        }
        return [...prev, ...toAdd];
      });

      if (autoOpenModal) {
        setIsShoppingModalOpen(true);
      }
    },
    []
  );

  const toggleItem = useCallback((id: string) => {
    setItems((prev) =>
      prev.map((item) => (item.id === id ? { ...item, checked: !item.checked } : item))
    );
  }, []);

  const removeItem = useCallback((id: string) => {
    setItems((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearCompleted = useCallback(() => {
    setItems((prev) => prev.filter((item) => !item.checked));
  }, []);

  const clearAll = useCallback(() => {
    setItems([]);
  }, []);

  const formatListText = useCallback((): string => {
    if (items.length === 0) return 'My WhatToCook Shopping List is currently empty!';

    const unchecked = items.filter((i) => !i.checked);
    const checked = items.filter((i) => i.checked);

    let text = '🛒 *WhatToCook - Smart Grocery List*\n\n';

    if (unchecked.length > 0) {
      text += '📋 *To Buy:*\n';
      unchecked.forEach((item) => {
        text += `• ${item.name} (${item.quantity || '1'})\n`;
      });
      text += '\n';
    }

    if (checked.length > 0) {
      text += '✅ *Purchased:*\n';
      checked.forEach((item) => {
        text += `• ~${item.name}~\n`;
      });
      text += '\n';
    }

    text += 'Generated by WhatToCook AI Recipe Generator';
    return text;
  }, [items]);

  const exportToWhatsApp = useCallback(() => {
    const text = encodeURIComponent(formatListText());
    window.open(`https://wa.me/?text=${text}`, '_blank');
  }, [formatListText]);

  const exportToTelegram = useCallback(() => {
    const text = encodeURIComponent(formatListText());
    window.open(`https://t.me/share/url?url=${text}`, '_blank');
  }, [formatListText]);

  const copyToClipboard = useCallback(async (): Promise<boolean> => {
    try {
      await navigator.clipboard.writeText(formatListText());
      return true;
    } catch {
      return false;
    }
  }, [formatListText]);

  const printList = useCallback(() => {
    window.print();
  }, []);

  // Stable context identity — consumers only re-render when a value they use changes.
  const value = useMemo<ShoppingListContextType>(
    () => ({
      items,
      isShoppingModalOpen,
      isTelegramModalOpen,
      openShoppingModal,
      closeShoppingModal,
      openTelegramModal,
      closeTelegramModal,
      addItem,
      addMultipleItems,
      toggleItem,
      removeItem,
      clearCompleted,
      clearAll,
      exportToWhatsApp,
      exportToTelegram,
      copyToClipboard,
      printList,
    }),
    [
      items,
      isShoppingModalOpen,
      isTelegramModalOpen,
      openShoppingModal,
      closeShoppingModal,
      openTelegramModal,
      closeTelegramModal,
      addItem,
      addMultipleItems,
      toggleItem,
      removeItem,
      clearCompleted,
      clearAll,
      exportToWhatsApp,
      exportToTelegram,
      copyToClipboard,
      printList,
    ]
  );

  return <ShoppingListContext.Provider value={value}>{children}</ShoppingListContext.Provider>;
};

export const useShoppingList = () => {
  const context = useContext(ShoppingListContext);
  if (!context) {
    throw new Error('useShoppingList must be used within a ShoppingListProvider');
  }
  return context;
};
