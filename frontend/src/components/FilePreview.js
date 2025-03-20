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
  Select,
  MenuItem,
  FormControl,
  InputLabel
} from '@mui/material';
import useFilePreview from '../hooks/useFilePreview';

/**
 * Component that displays a preview of the current netspeed CSV file
 */
function FilePreview() {
  // Define possible preview limits
  const previewLimits = [10, 25, 50, 100];

  // Use state to track the selected limit
  const [previewLimit, setPreviewLimit] = useState(100);

  // Use the hook with the dynamic limit
  const { previewData, loading, error } = useFilePreview(previewLimit);

  // Handle change in preview limit
  const handleLimitChange = (event) => {
    setPreviewLimit(Number(event.target.value));
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

  if (!previewData || !previewData.data || previewData.data.length === 0) {
    return (
      <Alert severity="info" sx={{ margin: '20px 0' }}>
        No data available for preview
      </Alert>
    );
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h5">
          CSV File Preview (First {previewData.data.length} Entries)
        </Typography>

        <FormControl variant="outlined" size="small" sx={{ minWidth: 120 }}>
          <InputLabel id="preview-limit-label">Show Entries</InputLabel>
          <Select
            labelId="preview-limit-label"
            value={previewLimit}
            onChange={handleLimitChange}
            label="Show Entries"
          >
            {previewLimits.map(limit => (
              <MenuItem key={limit} value={limit}>{limit}</MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>

      <Alert severity="info" sx={{ margin: '20px 0' }}>
        Showing first {previewData.data.length} entries of {previewData.line_count || previewData.data.length} total
      </Alert>

      <TableContainer
        component={Paper}
        sx={{
          margin: '20px 0',
          height: 'auto',
          maxHeight: 'none',
          overflow: 'auto',
          boxShadow: 3
        }}
      >
        <Table sx={{ width: 'auto', tableLayout: 'auto' }} aria-label="netspeed file preview table">
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
