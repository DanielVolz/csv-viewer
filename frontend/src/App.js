import React, { useState } from 'react';
import { 
  Container, 
  AppBar, 
  Toolbar, 
  Typography, 
  Box,
  CssBaseline
} from '@mui/material';
import Navigation from './components/Navigation';
import HomePage from './pages/HomePage';
import FilesPage from './pages/FilesPage';
import SettingsPage from './pages/SettingsPageSimple';
import DarkModeToggle from './components/DarkModeToggle';
import { SettingsProvider } from './contexts/SettingsContext';

function App() {
  const [currentTab, setCurrentTab] = useState('home');

  const handleTabChange = (event, newValue) => {
    setCurrentTab(newValue);
  };

  const renderContent = () => {
    switch (currentTab) {
      case 'files':
        return <FilesPage />;
      case 'settings':
        return <SettingsPage />;
      case 'home':
      default:
        return <HomePage />;
    }
  };

  return (
    <SettingsProvider>
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
                sx={{ 
                  fontWeight: 600,
                  color: 'text.primary'
                }}
              >
                CSV Viewer
              </Typography>
              
              <Navigation currentTab={currentTab} onTabChange={handleTabChange} />
            </Box>
            
            <DarkModeToggle />
          </Toolbar>
        </AppBar>

        {/* Main Content */}
        <Container maxWidth="xl" sx={{ pb: 4 }}>
          {/* Page Content */}
          {renderContent()}
        </Container>
      </Box>
    </SettingsProvider>
  );
}

export default App;
