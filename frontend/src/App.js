import React, { useState } from 'react';
import { 
  Container, 
  AppBar, 
  Toolbar, 
  Typography, 
  Box,
  CssBaseline
} from '@mui/material';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import FilesPage from './pages/FilesPage';
import SettingsPage from './pages/SettingsPageDnd';
import DarkModeToggle from './components/DarkModeToggle';
import { IconButton, Tooltip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';

function AppContent() {
  const [currentTab, setCurrentTab] = useState('home');
  const [homeRefreshKey, setHomeRefreshKey] = useState(0); // forces HomePage remount to refetch preview
  const { setNavigationFunction } = useSettings();

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  const goHomeAndRefresh = () => {
    setCurrentTab('home');
    // bump key to force HomePage subtree remount => FileInfoBox & CSVSearch re-run effects
    setHomeRefreshKey(k => k + 1);
  };

  // Set browser tab title once
  React.useEffect(() => {
    if (document && document.title !== 'CSV Viewer') {
      document.title = 'CSV Viewer';
    }
  }, []);

  // Register navigation function with settings context
  React.useEffect(() => {
    setNavigationFunction(handleTabChange);
  }, [setNavigationFunction]);

  const renderContent = () => {
    switch (currentTab) {
      case 'files':
        return <FilesPage />;
      case 'settings':
        return <SettingsPage />;
      case 'home':
      default:
        return <HomePage key={homeRefreshKey} />;
    }
  };

  return (
    <>
      <CssBaseline />
      <Box sx={{ 
        minHeight: '100vh',
        background: 'inherit',
        position: 'relative'
      }}>
        {/* Header */}
        <AppBar 
          position="static" 
          elevation={0}
          sx={{ 
            background: 'transparent',
            backdropFilter: 'blur(20px)',
            borderBottom: '1px solid',
            borderColor: 'divider',
            mb: 4
          }}
        >
          <Toolbar sx={{ py: 2 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', flexGrow: 1, gap: 4 }}>
              <Typography
                variant="h6"
                component="h1"
                onClick={goHomeAndRefresh}
                sx={{
                  fontWeight: 600,
                  color: 'text.primary',
                  cursor: 'pointer',
                  userSelect: 'none',
                  transition: 'opacity 0.15s',
                  '&:hover': { opacity: 0.7 }
                }}
              >
                CSV Viewer
              </Typography>
              
              <Navigation currentTab={currentTab} onTabChange={handleTabChange} />
            </Box>
            
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Tooltip title="Settings" arrow>
                <IconButton
                  size="small"
                  onClick={(e) => handleTabChange(e, 'settings')}
                  color={currentTab === 'settings' ? 'primary' : 'default'}
                >
                  <SettingsIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <DarkModeToggle />
            </Box>
          </Toolbar>
        </AppBar>

        {/* Main Content */}
        <Container maxWidth="xl" sx={{ pb: 4 }}>
          {/* Page Content */}
          {renderContent()}
        </Container>

        {/* Global Toast Container */}
        <ToastContainer
          position="top-right"
          autoClose={3000}
          hideProgressBar={false}
          newestOnTop={true}
          closeOnClick={true}
          rtl={false}
          pauseOnFocusLoss={true}
          draggable={true}
          pauseOnHover={true}
          limit={5}
          theme="colored"
          style={{
            marginTop: '60px' // Account for AppBar height
          }}
          toastStyle={{
            borderRadius: '12px',
            fontSize: '14px',
            fontWeight: '500',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.15)',
            backdropFilter: 'blur(10px)'
          }}
        />
      </Box>
    </>
  );
}

function App() {
  return (
    <SettingsProvider>
      <AppContent />
    </SettingsProvider>
  );
}

export default App;
