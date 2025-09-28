import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import useColumns from '../hooks/useColumns';

const SettingsContext = createContext();

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
          const sanitized = parsed.columns.filter(c => c && c.id);
          if (sanitized.length > 0) setColumns(sanitized);
        }
      }
    } catch (e) {
      // ignore parse errors
    }
  }, []);

  // Initialize columns from backend when available
  useEffect(() => {
    if (availableColumns && availableColumns.length > 0) {
      // Load saved settings from localStorage
      const savedSettings = localStorage.getItem('csv-viewer-settings');
      let savedColumns = null;

      if (savedSettings) {
        try {
          const parsed = JSON.parse(savedSettings);
          savedColumns = parsed.columns;
        } catch (error) {
          console.error('Error parsing saved settings:', error);
        }
      }

      // Merge backend columns with saved preferences preserving saved order
      let mergedColumns = [];
      if (Array.isArray(savedColumns) && savedColumns.length > 0) {
        // Use saved order; for each saved col, take backend definition if exists
        const backendById = new Map(availableColumns.map(c => [c.id, c]));
        mergedColumns = savedColumns
          .map(savedCol => {
            const backendCol = backendById.get(savedCol.id);
            if (!backendCol) return null; // drop unknown/removed columns
            return {
              ...backendCol,
              // preserve backend label (display name), ignore any stale saved label
              label: backendCol.label,
              enabled: typeof savedCol.enabled === 'boolean' ? savedCol.enabled : backendCol.enabled
            };
          })
          .filter(Boolean);

        // Append any new backend columns not present in saved settings
        const savedIds = new Set(savedColumns.map(c => c.id));
        const newOnes = availableColumns
          .filter(c => !savedIds.has(c.id))
          .map(c => ({ ...c }));
        mergedColumns = [...mergedColumns, ...newOnes];
      } else {
        // No saved settings; use backend order as-is
        mergedColumns = availableColumns.map(c => ({ ...c }));
      }

      setColumns(mergedColumns);
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
    const next = {
      ...prev,
      sshUsername,
      columns,
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
      const settings = {
        ...prev,
        sshUsername: nextSsh ?? sshUsername,
        columns: Array.isArray(nextColumns) ? nextColumns : columns
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
      persistSettings(undefined, next);
      return next;
    });
  }, [persistSettings]);

  // Allow explicit saving of columns (optional use by settings UI)
  const saveColumns = useCallback((nextColumns) => {
    if (Array.isArray(nextColumns)) setColumns(nextColumns);
  }, []);

  // Reorder columns
  const reorderColumns = useCallback((startIndex, endIndex) => {
    setColumns(prev => {
      const result = Array.from(prev);
      const [removed] = result.splice(startIndex, 1);
      result.splice(endIndex, 0, removed);
      persistSettings(undefined, result);
      return result;
    });
  }, [persistSettings]);

  // Reset to default configuration (reload from backend)
  const resetToDefault = useCallback(() => {
    if (availableColumns && availableColumns.length > 0) {
      const next = availableColumns.map(c => ({ ...c }));
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

  const value = useMemo(() => ({
    sshUsername,
    columns,
    columnsLoading,
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