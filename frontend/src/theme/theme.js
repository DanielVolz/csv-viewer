import { createTheme } from '@mui/material/styles';

// Define the light theme
export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2', // Blue color
    },
    secondary: {
      main: '#dc004e', // Pink color
    },
    background: {
      default: '#f5f5f5',
      paper: '#ffffff',
    },
    text: {
      primary: 'rgba(0, 0, 0, 0.87)',
      secondary: 'rgba(0, 0, 0, 0.6)',
    },
    info: {
      main: '#0288d1', // Blue for info alerts
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.05)',
          borderColor: 'rgba(0, 0, 0, 0.12)',
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        standardInfo: {
          backgroundColor: '#e3f2fd', // Light blue for info alerts
          color: '#0d47a1',
        },
        standardSuccess: {
          backgroundColor: '#e8f5e9', // Light green for success alerts
          color: '#1b5e20',
        },
        standardError: {
          backgroundColor: '#ffebee', // Light red for error alerts
          color: '#b71c1c',
        },
      },
    },
    MuiTable: {
      styleOverrides: {
        root: {
          borderSpacing: '0',
          borderCollapse: 'separate',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(224, 224, 224, 1)',
          padding: '12px 16px',
        },
        head: {
          fontWeight: 600,
          color: 'rgba(0, 0, 0, 0.87)',
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(odd)': {
            backgroundColor: '#fafafa',
          },
          '&:hover': {
            backgroundColor: 'rgba(0, 0, 0, 0.04) !important', // Hover highlight
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: '#f5f5f5',
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(0, 0, 0, 0.12)',
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          color: 'rgba(0, 0, 0, 0.54)',
        },
      },
    },
    MuiFormLabel: {
      styleOverrides: {
        root: {
          color: 'rgba(0, 0, 0, 0.6)',
        },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: 'rgba(0, 0, 0, 0.87)',
          },
        },
        notchedOutline: {
          borderColor: 'rgba(0, 0, 0, 0.23)',
        },
      },
    },
  },
});

// Define the dark theme
export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#90caf9', // Lighter blue for better contrast in dark mode
    },
    secondary: {
      main: '#f48fb1', // Lighter pink for better contrast in dark mode
    },
    background: {
      default: '#121212', // Dark background
      paper: '#1e1e1e',   // Slightly lighter for paper elements
    },
    text: {
      primary: '#ffffff',
      secondary: 'rgba(255, 255, 255, 0.7)',
    },
    info: {
      main: '#64b5f6', // Lighter blue for info alerts
    },
  },
  components: {
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: 'none', // Remove default paper elevation patterns
          borderColor: 'rgba(255, 255, 255, 0.15)', // Add border color for dark mode
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(48, 63, 76, 0.8)', // Darker background for alerts
        },
        standardInfo: {
          backgroundColor: '#1e3a5f', // Darker blue for info alerts
          color: '#ffffff',
        },
        standardSuccess: {
          backgroundColor: '#1e3c2f', // Darker green for success alerts
          color: '#ffffff',
        },
        standardError: {
          backgroundColor: '#4e2a32', // Darker red for error alerts
          color: '#ffffff',
        },
      },
    },
    MuiTable: {
      styleOverrides: {
        root: {
          borderSpacing: '0',
          borderCollapse: 'separate',
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderBottom: '1px solid rgba(255, 255, 255, 0.12)',
          padding: '12px 16px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        },
        head: {
          fontWeight: 600,
          color: '#ffffff',
          backgroundColor: 'rgba(48, 56, 70, 0.8)', // Consistent with TableHead
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(odd)': {
            backgroundColor: 'rgba(255, 255, 255, 0.05)', // Subtle alternating row color
          },
          '&:hover': {
            backgroundColor: 'rgba(255, 255, 255, 0.08) !important', // Hover highlight
          },
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: 'rgba(48, 56, 70, 0.8)', // Darker for table headers
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: '#1a1a2e', // Darker blue app bar
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: 'rgba(255, 255, 255, 0.12)', // Lighter divider for dark mode
        },
      },
    },
    MuiCheckbox: {
      styleOverrides: {
        root: {
          color: 'rgba(255, 255, 255, 0.7)',
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          color: '#ffffff',
        },
      },
    },
    MuiToolbar: {
      styleOverrides: {
        root: {
          color: '#ffffff',
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        root: {
          caretColor: '#ffffff', // Better cursor visibility
        },
      },
    },
  },
});
