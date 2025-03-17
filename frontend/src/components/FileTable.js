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
  Alert
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
    <TableContainer component={Paper} sx={{ margin: '20px 0' }}>
      <Table sx={{ minWidth: 650 }} aria-label="netspeed files table">
        <TableHead>
          <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
            <TableCell><Typography variant="subtitle1"><strong>File Name</strong></Typography></TableCell>
            <TableCell><Typography variant="subtitle1"><strong>Status</strong></Typography></TableCell>
            <TableCell><Typography variant="subtitle1"><strong>Path</strong></Typography></TableCell>
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
                  <span style={{ color: 'green', fontWeight: 'bold' }}>Current</span>
                ) : (
                  <span style={{ color: 'gray' }}>Historical</span>
                )}
              </TableCell>
              <TableCell>{file.path}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

export default FileTable;
