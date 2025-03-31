import React, { useState } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  Box,
  Chip,
  Button,
  Snackbar
} from '@mui/material';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import axios from 'axios';
import useFiles from '../hooks/useFiles';

/**
 * Component that displays a table of netspeed CSV files
 */
function FileTable() {
  const { files, loading, error, refetch } = useFiles();
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState('');
  const [openSnackbar, setOpenSnackbar] = useState(false);
  
  /**
   * Returns color for date display based on how recent the date is:
   * - Green for today's date
   * - Orange for dates within the next two weeks (including future and past dates)
   * - Red for dates older than 2 weeks in the past
   */
  const getDateColor = (dateString) => {
    if (!dateString) return 'inherit';
    
    const today = new Date();
    today.setHours(0, 0, 0, 0); // Reset time to start of day
    
    const fileDate = new Date(dateString);
    fileDate.setHours(0, 0, 0, 0); // Reset time to start of day
    
    // Calculate difference in days
    const diffTime = fileDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) {
      // Today
      return 'green';
    } else if (diffDays > 0 && diffDays <= 14) {
      // Future dates within next two weeks
      return 'orange';
    } else if (diffDays < 0 && diffDays >= -14) {
      // Past dates within previous two weeks
      return 'orange';
    } else {
      // Older dates (more than 2 weeks in the past)
      return 'red';
    }
  };
  
  const handleReindex = async () => {
    try {
      setReindexing(true);
      const response = await axios.get('/api/files/reindex');
      setReindexMessage(response.data.message || 'Reindexing in progress...');
      setOpenSnackbar(true);
      // Wait a moment and then refetch to show updated data
      setTimeout(() => {
        refetch();
        setReindexing(false);
      }, 2000);
    } catch (error) {
      console.error('Error triggering reindex:', error);
      setReindexMessage('Error triggering reindex. Please try again.');
      setOpenSnackbar(true);
      setReindexing(false);
    }
  };
  
  const handleCloseSnackbar = () => {
    setOpenSnackbar(false);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '20px' }}>
        <CircularProgress />
      </div>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ margin: '20px 0' }}>
        {error}
      </Alert>
    );
  }

  if (!files || files.length === 0) {
    return (
      <Typography variant="h6" align="center" sx={{ margin: '20px 0' }}>
        No files found
      </Typography>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">
          CSV File List
        </Typography>
        <Button 
          variant="contained" 
          color="primary" 
          onClick={handleReindex}
          disabled={reindexing}
        >
          {reindexing ? 'Reindexing...' : 'Reindex All Files'}
        </Button>
      </Box>
      
      <Snackbar
        open={openSnackbar}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        message={reindexMessage}
      />
      
      <Typography variant="body2" color="text.secondary" paragraph>
        The following CSV files are available. Files are listed with the current file first, 
        followed by historical files in descending order. Each file is automatically detected 
        to be in either the new format (14 columns) or old format (11 columns).
      </Typography>
      
      <TableContainer component={Paper} sx={{ margin: '20px 0' }}>
        <Table sx={{ tableLayout: 'fixed' }} aria-label="netspeed files table">
          <TableHead>
            <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
              <TableCell><Typography variant="subtitle1" noWrap><strong>File Name</strong></Typography></TableCell>
              <TableCell><Typography variant="subtitle1" noWrap><strong>Status</strong></Typography></TableCell>
              <TableCell><Typography variant="subtitle1" noWrap><strong>Format</strong></Typography></TableCell>
              <TableCell><Typography variant="subtitle1" noWrap><strong>Entries</strong></Typography></TableCell>
              <TableCell><Typography variant="subtitle1" noWrap><strong>File Creation Date</strong></Typography></TableCell>
              <TableCell><Typography variant="subtitle1" noWrap><strong>Path</strong></Typography></TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {files.map((file) => (
              <TableRow
                key={file.name}
                sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
              >
                <TableCell component="th" scope="row">
                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <a 
                      href={`/api/files/download/${file.name}`} 
                      download
                      style={{ 
                        display: 'flex',
                        alignItems: 'center',
                        color: 'inherit', 
                        textDecoration: 'underline',
                        cursor: 'pointer'
                      }}
                    >
                      <FileDownloadIcon 
                        fontSize="small" 
                        color="primary" 
                        sx={{ mr: 1 }}
                      />
                      {file.name}
                    </a>
                  </Box>
                </TableCell>
                <TableCell>
                  {file.is_current ? (
                    <Chip 
                      label="Current" 
                      color="success" 
                      size="small"
                      variant="outlined"
                    />
                  ) : (
                    <Chip 
                      label="Historical" 
                      color="default" 
                      size="small"
                      variant="outlined"
                    />
                  )}
                </TableCell>
                <TableCell>
                  {file.format === 'new' ? (
                    <Chip 
                      label="New Format (14 columns)" 
                      color="primary" 
                      size="small"
                      variant="outlined"
                    />
                  ) : (
                    <Chip 
                      label="Old Format (11 columns)" 
                      color="secondary" 
                      size="small"
                      variant="outlined"
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Typography>
                    {file.line_count ? file.line_count.toLocaleString() : '0'} lines
                  </Typography>
                </TableCell>
                <TableCell>
                  {file.date ? (
                    <Typography 
                      style={{ 
                        color: getDateColor(file.date) 
                      }}
                    >
                      {new Date(file.date).toISOString().split('T')[0]}
                    </Typography>
                  ) : 'N/A'}
                </TableCell>
                <TableCell>{file.path}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default FileTable;
