import React from 'react';
import { Box } from '@mui/material';
import FileTable from '../components/FileTable';
import FileInfoBox from '../components/FileInfoBox';

function FilesPage() {
  return (
    <Box>
      {/* File Info Section */}
      <Box sx={{ mb: 4 }}>
        <FileInfoBox />
      </Box>

      {/* File Table */}
      <FileTable />
    </Box>
  );
}

export default FilesPage;