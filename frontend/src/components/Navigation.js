import React from 'react';
import {
  Tabs,
  Tab
} from '@mui/material';
import { Home, Folder, BarChart } from '@mui/icons-material';

function Navigation({ currentTab, onTabChange, onHomeClick }) {
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
      />
      <Tab
        icon={<Folder fontSize="small" />}
        label="Files"
        value="files"
        iconPosition="start"
      />
      <Tab
        icon={<BarChart fontSize="small" />}
        label="Statistics"
        value="stats"
        iconPosition="start"
      />
    </Tabs>
  );
}

export default Navigation;