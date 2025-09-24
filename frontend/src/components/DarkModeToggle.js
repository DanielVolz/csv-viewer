import React from 'react';
import { IconButton, Tooltip, Box } from '@mui/material';
import { useTheme } from '../theme/ThemeContext';
import DarkModeOutlinedIcon from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlinedIcon from '@mui/icons-material/LightModeOutlined';

/**
 * Component for toggling between light and dark mode
 */
function DarkModeToggle() {
  const { isDarkMode, toggleTheme } = useTheme();


  const handleToggle = () => {
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
          aria-label={isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'}
          sx={(theme) => ({
            width: 38,
            height: 38,
            borderRadius: '999px',
            border: '1px solid',
            // High contrast in light mode, subtle in dark mode
            color: isDarkMode ? theme.palette.text.primary : theme.palette.primary.main,
            borderColor: isDarkMode ? 'rgba(148,163,184,0.32)' : '#cbd5e1',
            backgroundColor: isDarkMode ? 'transparent' : theme.palette.background.paper,
            transition: 'background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease',
            '&:hover': {
              backgroundColor: isDarkMode ? 'rgba(34,211,238,0.12)' : 'rgba(37, 99, 235, 0.08)',
              borderColor: theme.palette.primary.main,
              color: theme.palette.primary.main,
            },
            '&:focus-visible': {
              outline: `2px solid ${theme.palette.primary.main}`,
              outlineOffset: 2,
            },
          })}
        >
          {isDarkMode ? (
            <LightModeOutlinedIcon fontSize="small" />
          ) : (
            <DarkModeOutlinedIcon fontSize="small" />
          )}
        </IconButton>
      </Tooltip>
    </Box>
  );
}

export default DarkModeToggle;
