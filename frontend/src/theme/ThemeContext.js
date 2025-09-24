import React, { createContext, useContext, useState, useEffect } from 'react';
import { flushSync } from 'react-dom';
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
      return initialMode;
    } catch (error) {
      console.error('Error initializing theme:', error);
      return false;
    }
  });

  // Disable all CSS transitions briefly to avoid jank during theme switch
  const disableTransitionsBriefly = React.useCallback((timeoutMs = 200) => {
    try {
      const style = document.createElement('style');
      style.setAttribute('data-disable-transitions', 'true');
      style.appendChild(document.createTextNode('*{transition:none!important}'));
      document.head.appendChild(style);
      // Force reflow so the style takes effect immediately
      void window.getComputedStyle(document.documentElement).transition;
      window.setTimeout(() => {
        try { document.head.removeChild(style); } catch { }
      }, timeoutMs);
    } catch { }
  }, []);

  // Toggle between light and dark mode
  const toggleTheme = () => {
    // Prevent global repaint storms (instantly switch without animations)
    disableTransitionsBriefly(220);
    const willBeDark = !isDarkMode;
    // Commit theme state synchronously (atomic re-render)
    flushSync(() => { setIsDarkMode(willBeDark); });
    // Apply matching body class immediately after commit for a single-frame swap
    try {
      if (willBeDark) document.body.classList.add('dark-mode');
      else document.body.classList.remove('dark-mode');
    } catch { }
  };

  // Update localStorage when the theme changes
  useEffect(() => {
    try {
      localStorage.setItem('darkMode', String(isDarkMode));
      // Body class is handled synchronously in toggleTheme for atomic swap
    } catch (error) {
      console.error('Error saving theme preference:', error);
    }
  }, [isDarkMode]);

  // Apply the theme to the body when the component mounts
  useEffect(() => {
    return () => {
      // noop
    };
  }, []);

  // Provide the current theme and toggle function (classic MUI ThemeProvider)
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
