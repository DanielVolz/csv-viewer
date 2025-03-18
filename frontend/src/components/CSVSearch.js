import React, { useState } from 'react';
import { 
  Box, 
  TextField, 
  Button, 
  Typography, 
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  Pagination,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Grid
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';

/**
 * Component for searching CSV files and displaying results
 * Also shows the first 25 entries of the CSV file as initial results
 */
function CSVSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [includeHistorical, setIncludeHistorical] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const { 
    searchAll, 
    results, 
    allResults,
    loading: searchLoading, 
    error: searchError,
    pagination,
    setPage,
    setPageSize
  } = useSearchCSV();
  const { previewData, loading: previewLoading, error: previewError } = useFilePreview(25);

  const handleSearch = async () => {
    if (!searchTerm) return;
    const success = await searchAll(searchTerm, includeHistorical);
    if (success) setHasSearched(true);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" gutterBottom>
        CSV Search
      </Typography>
      
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
            <TextField
              label="Search Term"
              placeholder="Enter search term..."
              variant="outlined"
              fullWidth
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyPress={handleKeyPress}
              helperText="Search for any text across all fields in the CSV files"
              sx={{ mr: 2 }}
            />
            <Button 
              variant="contained" 
              color="primary" 
              onClick={handleSearch}
              startIcon={<SearchIcon />}
              sx={{ height: 56 }}
              disabled={searchLoading || !searchTerm}
            >
              Search
            </Button>
          </Box>
          
          <FormControlLabel
            control={
              <Checkbox
                checked={includeHistorical}
                onChange={(e) => setIncludeHistorical(e.target.checked)}
                color="primary"
              />
            }
            label="Include historical files in search"
          />
        </Box>
      </Paper>

      {/* Loading indicator */}
      {(searchLoading || previewLoading) && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Error message */}
      {(searchError || previewError) && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {searchError || previewError}
        </Alert>
      )}

      {/* Results table - Show search results or preview data */}
      {!searchLoading && !previewLoading && (hasSearched ? results : previewData) && (
        <Box>
          <Typography variant="h6" gutterBottom>
            {hasSearched ? "Search Results" : "CSV File Preview (First 25 Entries)"}
          </Typography>
          
          <Box sx={{ mb: 2 }}>
            <Alert 
              severity={hasSearched ? (results?.success ? "success" : "info") : "info"} 
              sx={{ mb: 2 }}
            >
              {hasSearched ? results?.message : (previewData?.message || "Showing first 25 entries from the CSV file")}
            </Alert>
            
            {/* Pagination Controls */}
            {hasSearched && results?.success && results?.pagination && (
              <Box sx={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 2
              }}>
                <Typography variant="body2">
                  Showing {results.pagination.currentStart} to {results.pagination.currentEnd} of {results.pagination.totalItems} results
                </Typography>
                
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <FormControl variant="outlined" size="small" sx={{ minWidth: 120 }}>
                    <InputLabel id="page-size-label">Page Size</InputLabel>
                    <Select
                      labelId="page-size-label"
                      value={pagination.pageSize}
                      onChange={(e) => setPageSize(e.target.value)}
                      label="Page Size"
                    >
                      <MenuItem value={10}>10</MenuItem>
                      <MenuItem value={25}>25</MenuItem>
                      <MenuItem value={50}>50</MenuItem>
                      <MenuItem value={100}>100</MenuItem>
                      <MenuItem value={250}>250</MenuItem>
                    </Select>
                  </FormControl>
                  
                  <Pagination 
                    count={pagination.totalPages} 
                    page={pagination.page}
                    onChange={(e, page) => setPage(page)}
                    color="primary"
                    showFirstButton
                    showLastButton
                  />
                </Box>
              </Box>
            )}
          </Box>
          
          {((hasSearched && results?.data && results?.headers) || 
             (!hasSearched && previewData?.data && previewData?.headers)) && (
            <TableContainer component={Paper} sx={{ margin: '20px 0', maxHeight: 600 }}>
              <Table stickyHeader sx={{ minWidth: 800 }} aria-label="data table">
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    {(hasSearched ? results.headers : previewData.headers).map((header) => (
                      <TableCell key={header}>
                        <Typography variant="subtitle2">
                          <strong>{header}</strong>
                        </Typography>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {hasSearched ? (
                    results.data === null ? (
                      <TableRow>
                        <TableCell colSpan={results.headers.length} align="center">
                          No data found
                        </TableCell>
                      </TableRow>
                    ) : Array.isArray(results.data) ? (
                      results.data.map((row, index) => (
                        <TableRow
                          key={index}
                          sx={{ '&:nth-of-type(odd)': { backgroundColor: '#fafafa' } }}
                        >
                          {results.headers.map((header) => {
                            // Handle special formatting for specific columns
                            let cellContent = row[header];
                            
                            // Format dates
                            if (header === "Creation Date" && cellContent) {
                              cellContent = new Date(cellContent).toLocaleString();
                            }
                            
                            return (
                              <TableCell key={`${index}-${header}`}>
                                {cellContent}
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      ))
                    ) : (
                      <TableRow>
                        {results.headers.map((header) => {
                          // Handle special formatting for specific columns
                          let cellContent = results.data[header];
                          
                          // Format dates
                          if (header === "Creation Date" && cellContent) {
                            cellContent = new Date(cellContent).toLocaleString();
                          }
                          
                          return (
                            <TableCell key={header}>
                              {cellContent}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    )
                  ) : (
                    previewData.data.map((row, index) => (
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
                          
                          return (
                            <TableCell key={`${index}-${header}`}>
                              {cellContent}
                            </TableCell>
                          );
                        })}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}
    </Box>
  );
}

export default CSVSearch;
