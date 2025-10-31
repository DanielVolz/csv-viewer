import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import useColumns from '../hooks/useColumns';
import { CATEGORY_ORDER, getCategoryLabel, getColumnCategory } from '../constants/columnCategories';

const SettingsContext = createContext();

const sanitizeColumns = (cols) => {
  if (!Array.isArray(cols)) return [];
  return cols
    .filter(col => col && col.id && col.id !== '#')
    .map(col => ({ ...col }));
};

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within a SettingsProvider');
  }
  return context;
};

export const SettingsProvider = ({ children }) => {
  const [sshUsername, setSshUsername] = useState('');
  const [columns, setColumns] = useState([]);
  const [navigationCallback, setNavigationCallback] = useState(null);

  // Load available columns from backend
  const {
    columns: availableColumns,
    loading: columnsLoading,
    error: columnsError,
    refreshColumns
  } = useColumns();

  // Eagerly load saved columns from localStorage on mount so preferences apply immediately
  useEffect(() => {
    if (process.env.NODE_ENV === 'test') return; // skip heavy localStorage on mount in tests
    try {
      const savedSettings = localStorage.getItem('csv-viewer-settings');
      if (savedSettings) {
        const parsed = JSON.parse(savedSettings);
        if (Array.isArray(parsed?.columns) && parsed.columns.length > 0) {
          const sanitized = sanitizeColumns(parsed.columns);
          if (sanitized.length > 0) setColumns(sanitized);
        }
      }
    } catch (e) {
      // ignore parse errors
    }
  }, []);

  // Initialize columns from backend when available
  useEffect(() => {
    const availableSanitized = sanitizeColumns(availableColumns);
    if (availableSanitized.length > 0) {
      // Load saved settings from localStorage
      const savedSettings = localStorage.getItem('csv-viewer-settings');
      let savedColumns = null;

      if (savedSettings) {
        try {
          const parsed = JSON.parse(savedSettings);
          savedColumns = sanitizeColumns(parsed.columns);
        } catch (error) {
          console.error('Error parsing saved settings:', error);
        }
      }

      // Merge backend columns with saved preferences
      // ALWAYS use backend as source of truth for available columns
      // Only preserve enabled/disabled state from saved settings
      let mergedColumns = [];

      if (Array.isArray(savedColumns) && savedColumns.length > 0) {
        const savedById = new Map(savedColumns.map(c => [c.id, c]));

        // Use backend order and columns, but preserve enabled states from saved settings
        mergedColumns = availableSanitized.map(backendCol => ({
          ...backendCol,
          enabled: savedById.has(backendCol.id)
            ? savedById.get(backendCol.id).enabled
            : backendCol.enabled
        }));
      } else {
        // No saved settings; use backend order and defaults as-is
        mergedColumns = availableSanitized.map(c => ({ ...c }));
      }

      setColumns(mergedColumns);
    } else {
      setColumns([]);
    }
  }, [availableColumns]);

  // Load SSH username from localStorage on mount
  useEffect(() => {
    if (process.env.NODE_ENV === 'test') return; // skip in tests
    const savedSettings = localStorage.getItem('csv-viewer-settings');
    if (savedSettings) {
      try {
        const { sshUsername: savedUsername } = JSON.parse(savedSettings);
        if (savedUsername) setSshUsername(savedUsername);
      } catch (error) {
        console.error('Error loading SSH username from localStorage:', error);
      }
    }
  }, []);

  // Save settings to localStorage whenever they change
  useEffect(() => {
    if (process.env.NODE_ENV === 'test') return; // skip storage churn in tests
    // Merge with any existing keys (e.g., statistics) to avoid dropping them
    let prev = {};
    try {
      prev = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
    } catch { prev = {}; }
    const sanitized = sanitizeColumns(Array.isArray(columns) ? columns : []);
    const next = {
      ...prev,
      sshUsername,
      columns: sanitized,
    };
    localStorage.setItem('csv-viewer-settings', JSON.stringify(next));
  }, [sshUsername, columns]);

  // Helper to persist immediately (used when actions might trigger a reload)
  const persistSettings = useCallback((nextSsh, nextColumns) => {
    try {
      let prev = {};
      try {
        prev = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      } catch { prev = {}; }
      const sanitizedColumns = sanitizeColumns(Array.isArray(nextColumns) ? nextColumns : columns);
      const settings = {
        ...prev,
        sshUsername: nextSsh ?? sshUsername,
        columns: sanitizedColumns
      };
      localStorage.setItem('csv-viewer-settings', JSON.stringify(settings));
    } catch { }
  }, [sshUsername, columns]);

  // Stats/Timeline preferences helpers (for Statistics page)
  const getStatisticsPrefs = useCallback(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      return saved.statistics || {};
    } catch { return {}; }
  }, []);

  const saveStatisticsPrefs = useCallback((partial) => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const nextStats = { ...(saved.statistics || {}), ...(partial || {}) };
      const next = { ...saved, statistics: nextStats };
      localStorage.setItem('csv-viewer-settings', JSON.stringify(next));
    } catch { }
  }, []);

  // Get enabled columns in order
  const getEnabledColumns = useCallback(() => {
    return columns.filter(col => col.enabled);
  }, [columns]);

  // Get enabled column headers as array
  const getEnabledColumnHeaders = useCallback(() => {
    return columns
      .filter(col => col.enabled)
      .map(col => col.id);
  }, [columns]);

  // Update column enabled status
  const toggleColumn = useCallback((columnId) => {
    setColumns(prev => {
      const next = prev.map(col => col.id === columnId ? { ...col, enabled: !col.enabled } : col);
      const sanitizedNext = sanitizeColumns(next);
      persistSettings(undefined, sanitizedNext);
      return sanitizedNext;
    });
  }, [persistSettings]);

  // Allow explicit saving of columns (optional use by settings UI)
  const saveColumns = useCallback((nextColumns) => {
    if (Array.isArray(nextColumns)) {
      const sanitized = sanitizeColumns(nextColumns);
      setColumns(sanitized);
      persistSettings(undefined, sanitized);
    }
  }, [persistSettings]);

  // Reorder columns
  const reorderColumns = useCallback((startIndex, endIndex) => {
    setColumns(prev => {
      const result = Array.from(prev);
      const [removed] = result.splice(startIndex, 1);
      result.splice(endIndex, 0, removed);
      const sanitizedResult = sanitizeColumns(result);
      persistSettings(undefined, sanitizedResult);
      return sanitizedResult;
    });
  }, [persistSettings]);

  // Reset to default configuration (reload from backend)
  const resetToDefault = useCallback(() => {
    if (availableColumns && availableColumns.length > 0) {
      const next = sanitizeColumns(availableColumns);
      setColumns(next);
      persistSettings(undefined, next);
    } else {
      refreshColumns();
    }
  }, [availableColumns, refreshColumns, persistSettings]);

  // Update SSH username
  const updateSshUsername = useCallback((username) => {
    setSshUsername(username);
    persistSettings(username, undefined);
  }, [persistSettings]);

  // Set navigation callback function
  const setNavigationFunction = useCallback((callback) => {
    setNavigationCallback(() => callback);
  }, []);

  // Navigate to settings
  const navigateToSettings = useCallback(() => {
    if (navigationCallback) {
      navigationCallback(null, 'settings');
    }
  }, [navigationCallback]);

  const enabledColumns = useMemo(() => columns.filter(col => col.enabled), [columns]);

  const categorizedColumns = useMemo(() => {
    const groups = new Map();
    columns.forEach((column) => {
      const categoryId = getColumnCategory(column.id);
      if (!groups.has(categoryId)) {
        groups.set(categoryId, []);
      }
      groups.get(categoryId).push(column);
    });

    const orderedCategoryIds = [...CATEGORY_ORDER];
    for (const key of groups.keys()) {
      if (!orderedCategoryIds.includes(key)) {
        orderedCategoryIds.push(key);
      }
    }

    return orderedCategoryIds
      .map((id) => ({
        id,
        label: getCategoryLabel(id),
        columns: groups.get(id) || []
      }))
      .filter((entry) => entry.columns.length > 0);
  }, [columns]);
  const value = useMemo(() => ({
    sshUsername,
    columns,
    columnsLoading,
    enabledColumns,
    categorizedColumns,
    columnsError,
    getEnabledColumns,
    getEnabledColumnHeaders,
    toggleColumn,
    saveColumns,
    reorderColumns,
    resetToDefault,
    updateSshUsername,
    setNavigationFunction,
    navigateToSettings,
    refreshColumns,
    getStatisticsPrefs,
    saveStatisticsPrefs
  }), [
    sshUsername,
    columns,
    columnsLoading,
    enabledColumns,
    categorizedColumns,
    columnsError,
    getEnabledColumns,
    getEnabledColumnHeaders,
    toggleColumn,
    saveColumns,
    reorderColumns,
    resetToDefault,
    updateSshUsername,
    setNavigationFunction,
    navigateToSettings,
    refreshColumns,
    getStatisticsPrefs,
    saveStatisticsPrefs
  ]);

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};

export default SettingsContext;