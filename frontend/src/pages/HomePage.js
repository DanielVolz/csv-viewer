import React from 'react';
import { Box } from '@mui/material';
import CSVSearch from '../components/CSVSearch';
import FileInfoBox from '../components/FileInfoBox';

function HomePage({ resetKey }) {
  return (
    <Box>
      {/* File Info Section */}
      <Box sx={{ mb: 2 }}>
        <FileInfoBox compact />
      </Box>

      {/* Search Section */}
      <Box sx={{ mb: 4 }}>
        <CSVSearch key={resetKey} />
      </Box>
    </Box>
  );
}

export default HomePage;