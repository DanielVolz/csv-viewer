import { useCallback, useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'csv_viewer_mac_history_v1';
const MAX_ITEMS = 5;

function safeNowIso() {
  try {
    return new Date().toISOString();
  } catch {
    return '';
  }
}

export default function useMacHistory() {
  const [items, setItems] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) return parsed;
      }
    } catch (e) {
      // ignore
    }
    return [];
  });

  // Persist on change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
    } catch (e) {
      // ignore storage errors
    }
  }, [items]);

  const record = useCallback((mac, loc) => {
    if (!mac || typeof mac !== 'string') return;
    const normalized = mac.trim().toLowerCase();
    if (!normalized) return;
    setItems(prev => {
      const next = [...prev];
      const idx = next.findIndex(x => (x && typeof x.mac === 'string') && x.mac.toLowerCase() === normalized);
      const now = safeNowIso();
      if (idx >= 0) {
        // update timestamp and count, keep original casing
        const existing = next[idx];
        next[idx] = {
          ...existing,
          lastSearchedAt: now,
          count: (existing.count || 0) + 1,
          ...(loc ? { loc } : {})
        };
      } else {
        next.unshift({ mac, lastSearchedAt: now, count: 1, ...(loc ? { loc } : {}) });
      }
      // trim
      if (next.length > MAX_ITEMS) next.length = MAX_ITEMS;
      // sort desc by lastSearchedAt
      next.sort((a, b) => String(b.lastSearchedAt).localeCompare(String(a.lastSearchedAt)));
      return next;
    });
  }, []);

  // Update one or more fields for an existing MAC entry without bumping counters/timestamps
  const update = useCallback((mac, patch) => {
    if (!mac || !patch) return;
    setItems(prev => {
      const idx = prev.findIndex(x => String(x.mac).toLowerCase() === String(mac).toLowerCase());
      if (idx === -1) return prev;
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  }, []);

  const remove = useCallback((mac) => {
    setItems(prev => prev.filter(x => String(x.mac).toLowerCase() !== String(mac).toLowerCase()));
  }, []);

  const clear = useCallback(() => {
    setItems([]);
  }, []);

  const list = useMemo(() => items, [items]);

  return { list, record, remove, clear, update };
}
