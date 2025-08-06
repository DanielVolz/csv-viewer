import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';

// Default available columns (from the CSV data structure)
const DEFAULT_AVAILABLE_COLUMNS = [
  { id: '#', label: '#', enabled: true },
  { id: 'File Name', label: 'File Name', enabled: true },
  { id: 'Creation Date', label: 'Creation Date', enabled: true },
  { id: 'IP Address', label: 'IP Address', enabled: true },
  { id: 'Line Number', label: 'Line Number', enabled: false },
  { id: 'MAC Address', label: 'MAC Address', enabled: true },
  { id: 'MAC Address 2', label: 'MAC Address 2', enabled: false },
  { id: 'Subnet Mask', label: 'Subnet Mask', enabled: false },
  { id: 'Voice VLAN', label: 'Voice VLAN', enabled: false },
  { id: 'Speed 1', label: 'Speed 1', enabled: false },
  { id: 'Speed 2', label: 'Speed 2', enabled: false },
  { id: 'Switch Hostname', label: 'Switch Hostname', enabled: true },
  { id: 'Switch Port', label: 'Switch Port', enabled: true },
  { id: 'Speed 3', label: 'Speed 3', enabled: false },
  { id: 'Speed 4', label: 'Speed 4', enabled: false },
  { id: 'Serial Number', label: 'Serial Number', enabled: false },
  { id: 'Model Name', label: 'Model Name', enabled: false }
];

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
  const [columns, setColumns] = useState(DEFAULT_AVAILABLE_COLUMNS);
  const [navigationCallback, setNavigationCallback] = useState(null);

  // Load settings from localStorage on mount
  useEffect(() => {
    const savedSettings = localStorage.getItem('csv-viewer-settings');
    if (savedSettings) {
      try {
        const { sshUsername: savedUsername, columns: savedColumns } = JSON.parse(savedSettings);
        if (savedUsername) setSshUsername(savedUsername);
        if (savedColumns && Array.isArray(savedColumns)) {
          setColumns(savedColumns);
        }
      } catch (error) {
        console.error('Error loading settings from localStorage:', error);
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

  // Reset to default configuration
  const resetToDefault = useCallback(() => {
    setColumns(DEFAULT_AVAILABLE_COLUMNS);
  }, []);

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
    getEnabledColumns,
    getEnabledColumnHeaders,
    toggleColumn,
    reorderColumns,
    resetToDefault,
    updateSshUsername,
    setNavigationFunction,
    navigateToSettings
  }), [
    sshUsername,
    columns,
    getEnabledColumns,
    getEnabledColumnHeaders,
    toggleColumn,
    reorderColumns,
    resetToDefault,
    updateSshUsername,
    setNavigationFunction,
    navigateToSettings
  ]);

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};

export default SettingsContext;