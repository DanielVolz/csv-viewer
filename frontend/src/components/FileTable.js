import React from 'react';
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
  Chip
} from '@mui/material';
import useFiles from '../hooks/useFiles';

/**
 * Component that displays a table of netspeed CSV files
 */
function FileTable() {
  const { files, loading, error } = useFiles();

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
      <Typography variant="h5" gutterBottom>
        CSV File List
      </Typography>
      
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
              <TableCell><Typography variant="subtitle1" noWrap><strong>Creation Date</strong></Typography></TableCell>
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
                  {file.name}
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
                  {file.name === 'netspeed.csv' ? (
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
                  {file.date ? new Date(file.date).toLocaleString() : 'N/A'}
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
