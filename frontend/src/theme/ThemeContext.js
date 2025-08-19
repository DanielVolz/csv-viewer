import React, { createContext, useContext, useState, useEffect } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { lightTheme, darkTheme } from './theme';
import { CssBaseline } from '@mui/material';

// Create a context for the theme
const ThemeContext = createContext({
  isDarkMode: false,
  toggleTheme: () => { },
});

// Create a provider component
export const ThemeProvider = ({ children }) => {
  // Check if dark mode was previously set in local storage
  const [isDarkMode, setIsDarkMode] = useState(() => {
    try {
      const savedMode = localStorage.getItem('darkMode');
      // Check if the browser/OS prefers dark mode
      const prefersDarkMode = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
      const initialMode = savedMode !== null ? savedMode === 'true' : prefersDarkMode;
      console.log('Initial dark mode:', initialMode);
      return initialMode;
    } catch (error) {
      console.error('Error initializing theme:', error);
      return false;
    }
  });

  // Toggle between light and dark mode
  const toggleTheme = () => {
    console.log('Toggling theme from', isDarkMode, 'to', !isDarkMode);
    setIsDarkMode(prevMode => !prevMode);
  };

  // Update localStorage when the theme changes
  useEffect(() => {
    try {
      localStorage.setItem('darkMode', String(isDarkMode));

      // Apply a class to the body element for additional styling
      if (isDarkMode) {
        document.body.classList.add('dark-mode');
        document.body.style.backgroundColor = '#121212';
        document.body.style.color = '#ffffff';
      } else {
        document.body.classList.remove('dark-mode');
        document.body.style.backgroundColor = '#f5f5f5';
        document.body.style.color = 'rgba(0, 0, 0, 0.87)';
      }

      console.log('Theme updated to:', isDarkMode ? 'dark' : 'light');
    } catch (error) {
      console.error('Error saving theme preference:', error);
    }
  }, [isDarkMode]);

  // Apply the theme to the body when the component mounts (debug logs only)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    console.log('ThemeProvider mounted, dark mode is:', isDarkMode);
    return () => {
      console.log('ThemeProvider unmounted');
    };
  }, []);

  // Provide the current theme and toggle function
  return (
    <ThemeContext.Provider value={{ isDarkMode, toggleTheme }}>
      <MuiThemeProvider theme={isDarkMode ? darkTheme : lightTheme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

// Custom hook to use the theme context
export const useTheme = () => useContext(ThemeContext);
