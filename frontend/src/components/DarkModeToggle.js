import React, { useEffect } from 'react';
import { 
  IconButton, 
  Tooltip, 
  Box,
  Badge
} from '@mui/material';
import { useTheme } from '../theme/ThemeContext';
import Brightness4Icon from '@mui/icons-material/Brightness4';  // Moon icon
import Brightness7Icon from '@mui/icons-material/Brightness7';  // Sun icon

/**
 * Component for toggling between light and dark mode
 */
function DarkModeToggle() {
  const { isDarkMode, toggleTheme } = useTheme();

  // Log theme state changes to console
  useEffect(() => {
    console.log('Dark mode is:', isDarkMode ? 'ON' : 'OFF');
  }, [isDarkMode]);

  const handleToggle = () => {
    console.log('Toggle theme clicked, current state:', isDarkMode);
    toggleTheme();
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 1,
        ml: 2,
      }}
    >
      <Tooltip title={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}>
        <IconButton 
          onClick={handleToggle} 
          color="inherit"
          aria-label={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
          sx={{
            backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.04)',
            '&:hover': {
              backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.08)',
            }
          }}
        >
          {isDarkMode ? <Brightness7Icon /> : <Brightness4Icon />}
        </IconButton>
      </Tooltip>
    </Box>
  );
}

export default DarkModeToggle;
