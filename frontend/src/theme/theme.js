import { createTheme, alpha } from '@mui/material/styles';

// Define the light theme with modern glassmorphism and premium colors
export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2563eb', // Professional blue
      light: '#3b82f6',
      dark: '#1d4ed8',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#64748b', // Subtle slate
      light: '#94a3b8',
      dark: '#475569',
      contrastText: '#ffffff',
    },
    background: {
      default: '#f8fafc',
      paper: '#ffffff',
    },
    text: {
      primary: '#1f2937',
      secondary: '#6b7280',
    },
    info: {
      main: '#3b82f6',
    },
    success: {
      main: '#10b981',
    },
    warning: {
      main: '#f59e0b',
    },
    error: {
      main: '#ef4444',
    },
  },
  typography: {
    fontFamily: '"Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    h1: {
      fontSize: '3.5rem',
      fontWeight: 800,
      color: '#1e293b',
      letterSpacing: '-0.025em',
    },
    h2: {
      fontSize: '2.5rem',
      fontWeight: 700,
      color: '#1f2937',
      letterSpacing: '-0.025em',
    },
    h3: {
      fontSize: '2rem',
      fontWeight: 600,
      color: '#374151',
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
      color: '#374151',
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
      color: '#4b5563',
    },
    h6: {
      fontSize: '1.125rem',
      fontWeight: 600,
      color: '#4b5563',
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
      color: '#6b7280',
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
      color: '#9ca3af',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background: '#f8fafc',
          minHeight: '100vh',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          background: '#ffffff',
          border: '1px solid #e2e8f0',
          borderRadius: '8px',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
          transition: 'box-shadow 0.2s ease',
          '&:hover': {
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: '#ffffff',
          borderBottom: '1px solid #e5e7eb',
          boxShadow: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '0.95rem',
          padding: '12px 24px',
          transition: 'background-color 0.2s ease, box-shadow 0.2s ease',
        },
        contained: {
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
          '&:hover': {
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
          },
        },
        outlined: {
          borderColor: '#cbd5e1',
          color: '#475569',
          '&:hover': {
            borderColor: '#2563eb',
            background: '#f1f5f9',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '12px',
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
            '&:hover': {
              background: '#f8fafc',
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#6366f1',
              },
            },
            '&.Mui-focused': {
              background: '#ffffff',
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#6366f1',
                borderWidth: '2px',
              },
            },
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
        },
        standardInfo: {
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(99, 102, 241, 0.1) 100%)',
          color: '#1e40af',
          borderColor: 'rgba(59, 130, 246, 0.2)',
        },
        standardSuccess: {
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.1) 0%, rgba(34, 197, 94, 0.1) 100%)',
          color: '#065f46',
          borderColor: 'rgba(16, 185, 129, 0.2)',
        },
        standardError: {
          background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.1) 100%)',
          color: '#991b1b',
          borderColor: 'rgba(239, 68, 68, 0.2)',
        },
        standardWarning: {
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1) 0%, rgba(251, 191, 36, 0.1) 100%)',
          color: '#92400e',
          borderColor: 'rgba(245, 158, 11, 0.2)',
        },
      },
    },
    MuiTable: {
      styleOverrides: {
        root: {
          borderSpacing: '0',
          borderCollapse: 'separate',
          borderRadius: '12px',
          overflow: 'hidden',
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          background: '#ffffff',
          border: '1px solid #e5e7eb',
          boxShadow: 'none',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(229, 231, 235, 0.8)',
          padding: '16px 20px',
          fontSize: '0.875rem',
        },
        head: {
          fontWeight: 700,
          color: '#374151',
          background: 'transparent',
          fontSize: '0.8rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.12s ease',
          '&:nth-of-type(odd)': {
            backgroundColor: 'rgba(249, 250, 251, 0.6)',
          },
          '&:hover': {
            backgroundColor: 'rgba(99, 102, 241, 0.08) !important',
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          background: 'transparent',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(229, 231, 235, 0.8)',
          margin: '24px 0',
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          color: '#6b7280',
          borderRadius: '6px',
          '&.Mui-checked': {
            color: '#6366f1',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        // function form to access ownerState for conditional styling
        root: ({ ownerState, theme }) => ({
          borderRadius: '8px',
          fontWeight: 600,
          fontSize: '0.75rem',
          // Make outlined success chips have green label/border; also ensure small label text is green
          ...(ownerState?.variant === 'outlined' && ownerState?.color === 'success' && {
            color: theme.palette.success.main,
            borderColor: theme.palette.success.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.success.main,
              fontWeight: 700,
            },
          }),
          // If success + small, prefer green label even if default
          ...(ownerState?.color === 'success' && ownerState?.size === 'small' && ownerState?.variant !== 'filled' && {
            '& .MuiChip-labelSmall': { color: theme.palette.success.main, fontWeight: 700 },
          }),
          // Ensure small filled success chips have green text, not white, with a subtle tinted bg
          ...(ownerState?.variant === 'filled' && ownerState?.color === 'success' && ownerState?.size === 'small' && {
            backgroundColor: alpha(theme.palette.success.main, 0.12),
            color: theme.palette.success.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.success.main,
              fontWeight: 700,
            },
            '& .MuiChip-icon, & .MuiChip-iconSmall': {
              color: theme.palette.success.main,
            },
          }),
          // Subtle orange style for small filled warning chips (e.g., Historical)
          ...(ownerState?.variant === 'filled' && ownerState?.color === 'warning' && ownerState?.size === 'small' && {
            backgroundColor: alpha(theme.palette.warning.main, 0.12),
            color: theme.palette.warning.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.warning.main,
              fontWeight: 700,
            },
            '& .MuiChip-icon, & .MuiChip-iconSmall': {
              color: theme.palette.warning.main,
            },
          }),
        }),
        labelSmall: {
          fontWeight: 600,
        },
      },
    },
    MuiPagination: {
      styleOverrides: {
        root: {
          '& .MuiPaginationItem-root': {
            borderRadius: '8px',
            fontWeight: 600,
            '&.Mui-selected': {
              backgroundColor: '#2563eb',
              color: '#ffffff',
            },
          },
        },
      },
    },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    '0 1px 3px rgba(0, 0, 0, 0.1)',
    '0 4px 6px rgba(0, 0, 0, 0.1)',
    '0 10px 15px rgba(0, 0, 0, 0.1)',
    '0 20px 25px rgba(0, 0, 0, 0.1)',
    '0 25px 50px rgba(0, 0, 0, 0.15)',
    // Add more shadows as needed
    ...Array(19).fill('0 25px 50px rgba(0, 0, 0, 0.15)'),
  ],
});

// Define the dark theme with professional aesthetic
export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#22d3ee', // cyan 400
      light: '#67e8f9',
      dark: '#06b6d4',
      contrastText: '#0d1117',
    },
    secondary: {
      main: '#a78bfa', // violet 300
      light: '#c4b5fd',
      dark: '#7c3aed',
      contrastText: '#0d1117',
    },
    background: {
      default: '#0d1117', // github dark base
      paper: '#0f172a',
    },
    text: {
      primary: '#e6edf3',
      secondary: '#9fb0c0',
    },
    divider: 'rgba(148,163,184,0.16)',
    info: { main: '#60a5fa' },
    success: { main: '#22c55e' },
    warning: { main: '#f59e0b' },
    error: { main: '#ef4444' },
  },
  typography: {
    fontFamily: '"Inter", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    h1: {
      fontSize: '3.5rem',
      fontWeight: 800,
      color: '#f1f5f9',
    },
    h2: {
      fontSize: '2.5rem',
      fontWeight: 700,
      color: '#e2e8f0',
      letterSpacing: '-0.025em',
    },
    h3: {
      fontSize: '2rem',
      fontWeight: 600,
      color: '#cbd5e1',
    },
    h4: {
      fontSize: '1.5rem',
      fontWeight: 600,
      color: '#cbd5e1',
    },
    h5: {
      fontSize: '1.25rem',
      fontWeight: 600,
      color: '#94a3b8',
    },
    h6: {
      fontSize: '1.125rem',
      fontWeight: 600,
      color: '#94a3b8',
    },
    body1: {
      fontSize: '1rem',
      lineHeight: 1.6,
      color: '#94a3b8',
    },
    body2: {
      fontSize: '0.875rem',
      lineHeight: 1.5,
      color: '#64748b',
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          background: '#0d1117',
          minHeight: '100vh',
        },
        '::selection': {
          backgroundColor: 'rgba(34,211,238,0.28)',
          color: '#ffffff',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          background: '#0f172a',
          border: '1px solid rgba(148,163,184,0.12)',
          borderRadius: '12px',
          boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
          transition: 'background-color 0.2s ease, border-color 0.2s ease',
          '&:hover': {
            backgroundColor: '#0f1b2e',
            borderColor: 'rgba(148,163,184,0.16)',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: '#0f172a',
          backdropFilter: 'none',
          borderBottom: '1px solid rgba(148,163,184,0.16)',
          boxShadow: 'none',
        },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '0.95rem',
          padding: '12px 24px',
          transition: 'background-color 0.15s ease, border-color 0.15s ease',
        },
        contained: {
          boxShadow: 'none',
          '&:hover': { boxShadow: 'none' },
        },
        containedPrimary: {
          background: '#22d3ee',
          color: '#0d1117',
          '&:hover': { background: '#06b6d4' },
        },
        outlined: {
          borderColor: 'rgba(148,163,184,0.28)',
          color: '#d1d5db',
          '&:hover': {
            borderColor: '#22d3ee',
            background: 'rgba(34, 211, 238, 0.10)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '10px',
            background: '#0b1628',
            border: '1px solid rgba(148,163,184,0.20)',
            transition: 'all 0.2s ease',
            '&:hover': {
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#22d3ee',
              },
            },
            '&.Mui-focused': {
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#22d3ee',
                borderWidth: '2px',
              },
            },
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: '10px',
          border: '1px solid',
        },
        standardInfo: {
          background: 'rgba(96,165,250,0.10)',
          color: '#93c5fd',
          borderColor: 'rgba(96,165,250,0.30)',
        },
        standardSuccess: {
          background: 'rgba(34,197,94,0.10)',
          color: '#34d399',
          borderColor: 'rgba(34,197,94,0.30)',
        },
        standardError: {
          background: 'rgba(239,68,68,0.10)',
          color: '#f87171',
          borderColor: 'rgba(239,68,68,0.30)',
        },
        standardWarning: {
          background: 'rgba(245,158,11,0.10)',
          color: '#fbbf24',
          borderColor: 'rgba(245,158,11,0.30)',
        },
      },
    },
    MuiTable: {
      styleOverrides: {
        root: {
          borderSpacing: '0',
          borderCollapse: 'separate',
          borderRadius: '12px',
          overflow: 'hidden',
        },
      },
    },
    MuiTableContainer: {
      styleOverrides: {
        root: {
          borderRadius: '12px',
          background: '#0f172a',
          border: '1px solid rgba(148,163,184,0.12)',
          boxShadow: '0 1px 2px rgba(0,0,0,0.4)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(148,163,184,0.14)',
          padding: '16px 20px',
          fontSize: '0.875rem',
          color: '#e6edf3',
        },
        head: {
          fontWeight: 700,
          color: '#e6edf3',
          background: 'rgba(34,211,238,0.10)',
          fontSize: '0.8rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.12s ease',
          '&:nth-of-type(odd)': {
            backgroundColor: 'rgba(255,255,255,0.02)',
          },
          '&:hover': {
            backgroundColor: 'rgba(255,255,255,0.04) !important',
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          background: 'rgba(34,211,238,0.10)',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(148,163,184,0.16)',
          margin: '24px 0',
          '&::before, &::after': {
            borderColor: 'rgba(148,163,184,0.16)',
          },
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          color: '#9fb0c0',
          borderRadius: '6px',
          '&.Mui-checked': {
            color: '#22d3ee',
          },
          '&:hover': {
            backgroundColor: 'rgba(34, 211, 238, 0.10)',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: ({ ownerState, theme }) => ({
          borderRadius: '8px',
          fontWeight: 600,
          fontSize: '0.75rem',
          background: 'rgba(148,163,184,0.10)',
          border: '1px solid rgba(148,163,184,0.18)',
          color: '#cbd5e1',
          // outlined success chips: green label and border in dark, too
          ...(ownerState?.variant === 'outlined' && ownerState?.color === 'success' && {
            color: theme.palette.success.main,
            borderColor: theme.palette.success.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.success.main,
              fontWeight: 700,
            },
          }),
          ...(ownerState?.color === 'success' && ownerState?.size === 'small' && ownerState?.variant !== 'filled' && {
            '& .MuiChip-labelSmall': { color: theme.palette.success.main, fontWeight: 700 },
          }),
          // Ensure small filled success chips have green text with subtle bg in dark mode as well
          ...(ownerState?.variant === 'filled' && ownerState?.color === 'success' && ownerState?.size === 'small' && {
            backgroundColor: alpha(theme.palette.success.main, 0.14),
            borderColor: alpha(theme.palette.success.main, 0.28),
            color: theme.palette.success.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.success.main,
              fontWeight: 700,
            },
            '& .MuiChip-icon, & .MuiChip-iconSmall': {
              color: theme.palette.success.main,
            },
          }),
          // Subtle orange style for small filled warning chips in dark mode
          ...(ownerState?.variant === 'filled' && ownerState?.color === 'warning' && ownerState?.size === 'small' && {
            backgroundColor: alpha(theme.palette.warning.main, 0.16),
            borderColor: alpha(theme.palette.warning.main, 0.30),
            color: theme.palette.warning.main,
            '& .MuiChip-label, & .MuiChip-labelSmall': {
              color: theme.palette.warning.main,
              fontWeight: 700,
            },
            '& .MuiChip-icon, & .MuiChip-iconSmall': {
              color: theme.palette.warning.main,
            },
          }),
        }),
        labelSmall: {
          fontWeight: 600,
        },
      },
    },
    MuiPagination: {
      styleOverrides: {
        root: {
          '& .MuiPaginationItem-root': {
            borderRadius: '8px',
            fontWeight: 600,
            color: '#d1d5db',
            border: '1px solid rgba(148,163,184,0.22)',
            '&.Mui-selected': {
              background: '#22d3ee',
              color: '#0d1117',
            },
            '&:hover': {
              backgroundColor: 'rgba(34, 211, 238, 0.10)',
              borderColor: '#22d3ee',
            },
          },
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: '#e2e8f0',
          '&:hover': {
            backgroundColor: 'rgba(34,211,238,0.10)',
            color: '#67e8f9',
          },
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: {
          color: '#e2e8f0',
        },
      },
    },
  },
  shape: {
    borderRadius: 12,
  },
  shadows: [
    'none',
    '0 1px 2px rgba(0, 0, 0, 0.35)',
    '0 3px 6px rgba(0, 0, 0, 0.35)',
    '0 8px 12px rgba(0, 0, 0, 0.35)',
    '0 16px 20px rgba(0, 0, 0, 0.38)',
    '0 20px 36px rgba(0, 0, 0, 0.50)',
    // Add more shadows as needed
    ...Array(19).fill('0 25px 40px rgba(0, 0, 0, 0.50)'),
  ],
});

// CSS Variables theme for fast, flicker-free color scheme switching
// Reuse existing light/dark palettes to avoid visual drift while moving to CssVarsProvider
// Removed cssVarsTheme; we are using classic ThemeProvider for stability
