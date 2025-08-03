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
import { Refresh, Download } from '@mui/icons-material';
import axios from 'axios';
import useFiles from '../hooks/useFiles';

function FileTable() {
  const { files, loading, error, refetch } = useFiles();
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState('');
  const [openSnackbar, setOpenSnackbar] = useState(false);

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const response = await axios.post('/api/files/reindex');
      setReindexMessage(response.data.message || 'Reindexing started successfully');
      setOpenSnackbar(true);
      // Refresh the file list after a short delay
      setTimeout(() => {
        refetch();
      }, 2000);
    } catch (error) {
      setReindexMessage('Error starting reindex: ' + (error.response?.data?.message || error.message));
      setOpenSnackbar(true);
    } finally {
      setReindexing(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getFileStatus = (file) => {
    if (file.name === 'netspeed.csv') {
      return { label: 'Active', color: 'success' };
    } else if (file.name.includes('_bak')) {
      return { label: 'Backup', color: 'warning' };
    } else {
      return { label: 'Historical', color: 'info' };
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {error}
      </Alert>
    );
  }

  return (
    <Box>
      <Snackbar
        open={openSnackbar}
        autoHideDuration={6000}
        onClose={() => setOpenSnackbar(false)}
        message={reindexMessage}
      />

      {/* Header Section */}
      <Box sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        mb: 3
      }}>
        <Typography variant="h6" fontWeight={600}>
          Files
        </Typography>
        <Button
          variant="contained"
          onClick={handleReindex}
          disabled={reindexing}
          startIcon={reindexing ? <CircularProgress size={20} /> : <Refresh />}
          size="small"
        >
          {reindexing ? 'Reindexing...' : 'Reindex'}
        </Button>
      </Box>

      {/* File Table */}
      <TableContainer component={Paper} elevation={1}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>File Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Created</TableCell>
              <TableCell>Records</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {files && files.length > 0 ? (
              files.map((file, index) => {
                const status = getFileStatus(file);
                return (
                  <TableRow key={index} hover>
                    <TableCell>
                      <Typography 
                        variant="body2" 
                        fontWeight={500}
                        component="a"
                        href={`/api/files/download/${file.name}`}
                        download
                        sx={{
                          textDecoration: 'underline',
                          color: 'primary.main',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          '&:hover': {
                            color: 'primary.dark'
                          }
                        }}
                      >
                        <Download fontSize="small" />
                        {file.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={status.label}
                        color={status.color}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {file.date ? new Date(file.date).toLocaleDateString() : '-'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {file.line_count ? file.line_count.toLocaleString() : '-'}
                      </Typography>
                    </TableCell>
                  </TableRow>
                );
              })
            ) : (
              <TableRow>
                <TableCell colSpan={4} align="center">
                  <Box sx={{ py: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                      No files found
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default FileTable;