import React from 'react';
import {
  Tabs,
  Tab
} from '@mui/material';
import { Home, Folder, BarChart } from '@mui/icons-material';

function Navigation({ currentTab, onTabChange, onHomeClick }) {
  // Open route in a new tab on middle-click without affecting current tab state
  const handleMiddleClick = (path) => (event) => {
    if (event && event.button === 1) {
      event.preventDefault();
      event.stopPropagation();
      try {
        window.open(path, '_blank', 'noopener');
      } catch {}
    }
  };

  return (
    <Tabs
      value={currentTab}
      onChange={onTabChange}
      variant="standard"
      sx={{
        minHeight: 'auto',
        display: 'flex',
        '& .MuiTabs-flexContainer': {
          alignItems: 'center'
        },
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
        label="Search"
        value="home"
        iconPosition="start"
        onClick={onHomeClick}
  onMouseDown={handleMiddleClick('/search')}
      />
      <Tab
        icon={<Folder fontSize="small" />}
        label="Files"
        value="files"
        iconPosition="start"
  onMouseDown={handleMiddleClick('/files')}
      />
      <Tab
        icon={<BarChart fontSize="small" />}
        label="Statistics"
        value="stats"
        iconPosition="start"
  onMouseDown={handleMiddleClick('/statistics')}
      />
    </Tabs>
  );
}

export default Navigation;