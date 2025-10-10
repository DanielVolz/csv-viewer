import React from 'react';
import { Paper, Typography, Box, Alert } from '@mui/material';
import { ErrorOutline, WarningAmber, InfoOutlined } from '@mui/icons-material';

/**
 * Unified error display component for consistent error messaging across the application
 *
 * @param {Object} props
 * @param {string} props.type - Type of error: 'error', 'warning', 'info'
 * @param {string} props.title - Main error title
 * @param {string} props.message - Detailed error message
 * @param {string} props.variant - Display variant: 'paper' (centered card) or 'alert' (inline alert)
 * @param {Object} props.sx - Additional MUI sx styling
 */
function ErrorDisplay({
  type = 'error',
  title,
  message,
  variant = 'paper',
  sx = {}
}) {
  const iconMap = {
    error: <ErrorOutline sx={{ fontSize: 48, mb: 2, opacity: 0.7 }} />,
    warning: <WarningAmber sx={{ fontSize: 48, mb: 2, opacity: 0.7 }} />,
    info: <InfoOutlined sx={{ fontSize: 48, mb: 2, opacity: 0.7 }} />
  };

  const severityMap = {
    error: 'error',
    warning: 'warning',
    info: 'info'
  };

  if (variant === 'alert') {
    return (
      <Alert
        severity={severityMap[type]}
        sx={{ mb: 3, ...sx }}
      >
        {title && (
          <Typography variant="subtitle2" fontWeight={600} gutterBottom>
            {title}
          </Typography>
        )}
        {message && (
          <Typography variant="body2">
            {message}
          </Typography>
        )}
      </Alert>
    );
  }

  // Paper variant (centered card)
  return (
    <Paper
      elevation={1}
      sx={{
        p: 4,
        textAlign: 'center',
        borderRadius: 2,
        border: '1px solid',
        borderColor: type === 'error' ? 'error.main' : type === 'warning' ? 'warning.main' : 'info.main',
        bgcolor: (theme) =>
          type === 'error'
            ? theme.palette.mode === 'dark' ? 'rgba(211, 47, 47, 0.05)' : 'rgba(211, 47, 47, 0.02)'
            : type === 'warning'
            ? theme.palette.mode === 'dark' ? 'rgba(237, 108, 2, 0.05)' : 'rgba(237, 108, 2, 0.02)'
            : theme.palette.mode === 'dark' ? 'rgba(2, 136, 209, 0.05)' : 'rgba(2, 136, 209, 0.02)',
        ...sx
      }}
    >
      <Box sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        color: type === 'error' ? 'error.main' : type === 'warning' ? 'warning.main' : 'info.main'
      }}>
        {iconMap[type]}

        {title && (
          <Typography variant="h6" gutterBottom fontWeight={600}>
            {title}
          </Typography>
        )}

        {message && (
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ maxWidth: 600, mt: 1 }}
          >
            {message}
          </Typography>
        )}
      </Box>
    </Paper>
  );
}

export default ErrorDisplay;
