import React from 'react';
import { 
  Tabs,
  Tab
} from '@mui/material';
import { Home, Folder, Settings } from '@mui/icons-material';

function Navigation({ currentTab, onTabChange }) {
  return (
    <Tabs 
      value={currentTab} 
      onChange={onTabChange}
      variant="standard"
      sx={{
        minHeight: 'auto',
        '& .MuiTabs-indicator': {
          height: 2
        },
        '& .MuiTab-root': {
          minHeight: 'auto',
          textTransform: 'none',
          fontWeight: 500,
          fontSize: '0.875rem',
          py: 1,
          px: 2
        }
      }}
    >
      <Tab 
        icon={<Home fontSize="small" />} 
        label="Home" 
        value="home"
        iconPosition="start"
      />
      <Tab 
        icon={<Folder fontSize="small" />} 
        label="Files" 
        value="files"
        iconPosition="start"
      />
      <Tab 
        icon={<Settings fontSize="small" />} 
        label="Settings" 
        value="settings"
        iconPosition="start"
      />
    </Tabs>
  );
}

export default Navigation;