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
  Box
} from '@mui/material';
import useFilePreview from '../hooks/useFilePreview';

/**
 * Component that displays a preview of the current netspeed CSV file
 */
function FilePreview() {
  const { previewData, loading, error } = useFilePreview(25); // Load first 25 entries

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

  if (!previewData || !previewData.data || previewData.data.length === 0) {
    return (
      <Alert severity="info" sx={{ margin: '20px 0' }}>
        No data available for preview
      </Alert>
    );
  }

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        CSV File Preview
      </Typography>
      
      <Alert severity="info" sx={{ margin: '20px 0' }}>
        {previewData.message}
      </Alert>
      
      <TableContainer component={Paper} sx={{ margin: '20px 0', maxHeight: 600 }}>
        <Table stickyHeader sx={{ minWidth: 800 }} aria-label="netspeed file preview table">
          <TableHead>
            <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
              {previewData.headers.map((header) => (
                <TableCell key={header}>
                  <Typography variant="subtitle2">
                    <strong>{header}</strong>
                  </Typography>
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {previewData.data.map((row, index) => (
              <TableRow
                key={index}
                sx={{ '&:nth-of-type(odd)': { backgroundColor: '#fafafa' } }}
              >
                {previewData.headers.map((header) => {
                  // Handle special formatting for specific columns
                  let cellContent = row[header];
                  
                  // Format dates
                  if (header === "Creation Date" && cellContent) {
                    cellContent = new Date(cellContent).toLocaleString();
                  }
                  
                  // Format MAC addresses with colons
                  if ((header === "MAC Address" || header === "MAC Address 2") && cellContent) {
                    if (cellContent.length === 12 && !cellContent.includes(':')) {
                      const formattedMac = cellContent.match(/.{1,2}/g).join(':').toUpperCase();
                      cellContent = formattedMac;
                    }
                  }
                  
                  return (
                    <TableCell key={`${index}-${header}`}>
                      {cellContent}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default FilePreview;
