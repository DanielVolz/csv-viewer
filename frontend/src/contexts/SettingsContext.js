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

      // Merge backend columns with saved preferences
      const mergedColumns = availableColumns.map(backendCol => {
        // Find matching saved column
        const savedCol = savedColumns?.find(col => col.id === backendCol.id);
        return {
          ...backendCol,
          enabled: savedCol ? savedCol.enabled : backendCol.enabled
        };
      });

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

  // Get enabled columns in order
  const getEnabledColumns = useCallback(() => {
    return columns.filter(col => col.enabled);
  }, [columns]);

  // Get enabled column headers as array
  const getEnabledColumnHeaders = useCallback(() => {
    return columns.filter(col => col.enabled).map(col => col.id);
  }, [columns]);

  // Update column enabled status
  const toggleColumn = useCallback((columnId) => {
    setColumns(prev => prev.map(col =>
      col.id === columnId ? { ...col, enabled: !col.enabled } : col
    ));
  }, []);

  // Reorder columns
  const reorderColumns = useCallback((startIndex, endIndex) => {
    setColumns(prev => {
      const result = Array.from(prev);
      const [removed] = result.splice(startIndex, 1);
      result.splice(endIndex, 0, removed);
      return result;
    });
  }, []);

  // Reset to default configuration (reload from backend)
  const resetToDefault = useCallback(() => {
    if (availableColumns && availableColumns.length > 0) {
      setColumns([...availableColumns]);
    } else {
      refreshColumns();
    }
  }, [availableColumns, refreshColumns]);

  // Update SSH username
  const updateSshUsername = useCallback((username) => {
    setSshUsername(username);
  }, []);

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