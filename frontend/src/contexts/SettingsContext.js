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
    try {
      const savedSettings = localStorage.getItem('csv-viewer-settings');
      if (savedSettings) {
        const parsed = JSON.parse(savedSettings);
        if (Array.isArray(parsed?.columns) && parsed.columns.length > 0) {
          const sanitized = parsed.columns.filter(c => c?.id !== 'MAC Address 2');
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
        // Remove columns intentionally hidden from settings
        savedColumns = savedColumns.filter(c => c?.id !== 'MAC Address 2');
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
    const settings = {
      sshUsername,
      columns
    };
    localStorage.setItem('csv-viewer-settings', JSON.stringify(settings));
  }, [sshUsername, columns]);

  // Helper to persist immediately (used when actions might trigger a reload)
  const persistSettings = useCallback((nextSsh, nextColumns) => {
    try {
      const settings = {
        sshUsername: nextSsh ?? sshUsername,
        columns: Array.isArray(nextColumns) ? nextColumns : columns
      };
      localStorage.setItem('csv-viewer-settings', JSON.stringify(settings));
    } catch { }
  }, [sshUsername, columns]);

  // Get enabled columns in order
  const getEnabledColumns = useCallback(() => {
    return columns.filter(col => col.enabled && col.id !== 'MAC Address 2');
  }, [columns]);

  // Get enabled column headers as array
  const getEnabledColumnHeaders = useCallback(() => {
    return columns
      .filter(col => col.enabled && col.id !== 'MAC Address 2')
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
      const next = availableColumns.filter(c => c.id !== 'MAC Address 2');
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
    refreshColumns
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
    refreshColumns
  ]);

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};

export default SettingsContext;