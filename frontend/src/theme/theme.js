import { createTheme } from '@mui/material/styles';

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
          background: 'rgba(255, 255, 255, 0.1)',
          backdropFilter: 'blur(20px)',
          border: 'none',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
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
          borderRadius: '16px',
          background: 'rgba(255, 255, 255, 0.9)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.15)',
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
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.05) 0%, rgba(139, 92, 246, 0.05) 100%)',
          fontSize: '0.8rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:nth-of-type(odd)': {
            backgroundColor: 'rgba(249, 250, 251, 0.6)',
          },
          '&:hover': {
            backgroundColor: 'rgba(99, 102, 241, 0.08) !important',
            transform: 'scale(1.01)',
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%)',
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
        root: {
          borderRadius: '8px',
          fontWeight: 600,
          fontSize: '0.75rem',
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
      main: '#3b82f6', // Professional blue
      light: '#60a5fa',
      dark: '#2563eb',
      contrastText: '#ffffff',
    },
    secondary: {
      main: '#6b7280', // Professional gray
      light: '#9ca3af',
      dark: '#4b5563',
      contrastText: '#ffffff',
    },
    background: {
      default: '#111827',
      paper: '#1f2937',
    },
    text: {
      primary: '#f9fafb',
      secondary: '#d1d5db',
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
          background: '#111827',
          minHeight: '100vh',
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          background: '#1f2937',
          border: '1px solid #374151',
          borderRadius: '8px',
          boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.3), 0 1px 2px 0 rgba(0, 0, 0, 0.2)',
          transition: 'all 0.2s ease',
          '&:hover': {
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3), 0 2px 4px -1px rgba(0, 0, 0, 0.2)',
          },
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: 'rgba(31, 41, 55, 0.95)',
          backdropFilter: 'blur(10px)',
          border: 'none',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3)',
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
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
          '&:hover': {
            boxShadow: '0 6px 8px rgba(0, 0, 0, 0.15)',
          },
        },
        outlined: {
          borderColor: '#4b5563',
          color: '#d1d5db',
          '&:hover': {
            borderColor: '#3b82f6',
            background: 'rgba(59, 130, 246, 0.1)',
          },
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          '& .MuiOutlinedInput-root': {
            borderRadius: '8px',
            background: '#1f2937',
            border: '1px solid #374151',
            transition: 'all 0.2s ease',
            '&:hover': {
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#3b82f6',
              },
            },
            '&.Mui-focused': {
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: '#3b82f6',
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
          borderRadius: '8px',
          border: '1px solid',
        },
        standardInfo: {
          background: 'rgba(59, 130, 246, 0.1)',
          color: '#60a5fa',
          borderColor: 'rgba(59, 130, 246, 0.3)',
        },
        standardSuccess: {
          background: 'rgba(16, 185, 129, 0.1)',
          color: '#34d399',
          borderColor: 'rgba(16, 185, 129, 0.3)',
        },
        standardError: {
          background: 'rgba(239, 68, 68, 0.1)',
          color: '#f87171',
          borderColor: 'rgba(239, 68, 68, 0.3)',
        },
        standardWarning: {
          background: 'rgba(245, 158, 11, 0.1)',
          color: '#fbbf24',
          borderColor: 'rgba(245, 158, 11, 0.3)',
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
          borderRadius: '8px',
          background: '#1f2937',
          border: '1px solid #374151',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.3)',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid #374151',
          padding: '16px 20px',
          fontSize: '0.875rem',
          color: '#f9fafb',
        },
        head: {
          fontWeight: 700,
          color: '#e5e7eb',
          background: '#4b5563',
          fontSize: '0.8rem',
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          transition: 'background-color 0.15s ease',
          '&:nth-of-type(odd)': {
            backgroundColor: '#374151',
          },
          '&:hover': {
            backgroundColor: 'rgba(59, 130, 246, 0.1) !important',
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          background: '#4b5563',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: '#374151',
          margin: '24px 0',
          '&::before, &::after': {
            borderColor: '#374151',
          },
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          color: '#9ca3af',
          borderRadius: '6px',
          '&.Mui-checked': {
            color: '#3b82f6',
          },
          '&:hover': {
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: '8px',
          fontWeight: 600,
          fontSize: '0.75rem',
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
            border: '1px solid #4b5563',
            '&.Mui-selected': {
              backgroundColor: '#3b82f6',
              color: '#ffffff',
            },
            '&:hover': {
              backgroundColor: 'rgba(59, 130, 246, 0.1)',
              borderColor: '#3b82f6',
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
            backgroundColor: 'rgba(139, 92, 246, 0.1)',
            color: '#8b5cf6',
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
    '0 1px 3px rgba(0, 0, 0, 0.3)',
    '0 4px 6px rgba(0, 0, 0, 0.3)',
    '0 10px 15px rgba(0, 0, 0, 0.3)',
    '0 20px 25px rgba(0, 0, 0, 0.3)',
    '0 25px 50px rgba(0, 0, 0, 0.5)',
    // Add more shadows as needed
    ...Array(19).fill('0 25px 50px rgba(0, 0, 0, 0.5)'),
  ],
});
