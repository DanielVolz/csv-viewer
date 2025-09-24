import React, { useState } from 'react';
import { Routes, Route, useLocation, useNavigate, Navigate, MemoryRouter, BrowserRouter } from 'react-router-dom';
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
import StatisticsPage from './pages/StatisticsPage';
import DarkModeToggle from './components/DarkModeToggle';
import { IconButton, Tooltip } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import useUpdateNotifier from './hooks/useUpdateNotifier';

function AppContent() {
  // Check for new deployments periodically (dev + prod)
  useUpdateNotifier({ intervalMs: 60000 });
  const location = useLocation();
  const navigate = useNavigate();
  const [currentTab, setCurrentTab] = useState('home');
  const [searchResetKey, setSearchResetKey] = useState(0);
  const { setNavigationFunction } = useSettings();

  const handleTabChange = React.useCallback((event, newValue) => {
    if (newValue === 'home') {
      // Clear any query params (e.g., ?q=...) and soft-reset the search without full reload
      try {
        const cleanPath = '/search';
        navigate(cleanPath, { replace: true });
      } catch { }
      setCurrentTab('home');
      setSearchResetKey((k) => k + 1);
      return;
    }
    setCurrentTab(newValue);
    // Push route for non-home tabs
    try {
      if (newValue === 'files') navigate('/files');
      else if (newValue === 'stats') navigate('/statistics');
      else if (newValue === 'settings') navigate('/settings');
    } catch { }
  }, [navigate]);

  const goHomeAndRefresh = React.useCallback(() => {
    // Clear any query params (e.g., ?q=...) and soft-reset the search without full reload
    try {
      navigate('/search', { replace: true });
    } catch { }
    setCurrentTab('home');
    setSearchResetKey((k) => k + 1);
  }, [navigate]);

  // Set browser tab title once
  React.useEffect(() => {
    if (document && document.title !== 'CSV Viewer') {
      document.title = 'CSV Viewer';
    }
  }, []);

  // Register navigation function with settings context
  React.useEffect(() => {
    setNavigationFunction(handleTabChange);
  }, [setNavigationFunction, handleTabChange]);

  // Sync currentTab with URL on first load and when location changes (back/forward)
  React.useEffect(() => {
    const path = location.pathname || '/';
    if (path === '/' || path === '/search') setCurrentTab('home');
    else if (path.startsWith('/files')) setCurrentTab('files');
    else if (path.startsWith('/statistics')) setCurrentTab('stats');
    else if (path.startsWith('/settings')) setCurrentTab('settings');
  }, [location.pathname]);

  // content selection handled via routes below

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

              <Navigation currentTab={currentTab} onTabChange={handleTabChange} onHomeClick={goHomeAndRefresh} />
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

        {/* Main Content with router */}
        <Container maxWidth="xl" sx={{ pb: 4 }}>
          <Routes>
            <Route path="/" element={<Navigate to="/search" replace />} />
            <Route path="/search" element={<HomePage resetKey={searchResetKey} />} />
            <Route path="/files" element={<FilesPage />} />
            <Route path="/statistics/*" element={<StatisticsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<Navigate to="/search" replace />} />
          </Routes>
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
  const content = <AppContent />;
  const wrapped = process.env.NODE_ENV === 'test'
    ? (<MemoryRouter initialEntries={["/search"]}>{content}</MemoryRouter>)
    : (<BrowserRouter>{content}</BrowserRouter>);
  return (
    <SettingsProvider>
      {wrapped}
    </SettingsProvider>
  );
}

export default App;
