import React from 'react';
import { Box } from '@mui/material';
import CSVSearch from '../components/CSVSearch';
import FileInfoBox from '../components/FileInfoBox';

function HomePage() {
  return (
    <Box>
      {/* File Info Section */}
      <Box sx={{ mb: 2 }}>
        <FileInfoBox compact />
      </Box>

      {/* Search Section */}
      <Box sx={{ mb: 4 }}>
        <CSVSearch />
      </Box>
    </Box>
  );
}

export default HomePage;