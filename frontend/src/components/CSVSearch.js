import React, { useState, useCallback, useRef } from 'react';
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
  InputLabel
} from '@mui/material';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';

/**
 * Component for searching CSV files and displaying results
 * Also shows the first 100 entries of the CSV file as initial results
 */
function CSVSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [includeHistorical, setIncludeHistorical] = useState(true);
  const [hasSearched, setHasSearched] = useState(false);
  const searchFieldRef = useRef(null);
  const {
    searchAll,
    results,
    loading: searchLoading,
    error: searchError,
    pagination,
    setPage,
    setPageSize
  } = useSearchCSV();
  const { previewData, loading: previewLoading, error: previewError } = useFilePreview();

  // Track typing activity
  const typingTimeoutRef = useRef(null);
  // Store last executed search term
  const lastSearchTermRef = useRef('');
  // Track if user is in the middle of typing
  const [isTyping, setIsTyping] = useState(false);

  // Function to actually execute search after user has stopped typing
  const executeSearch = useCallback((term) => {
    // Only search if term is valid and different from last search
    if (term.length >= 3 && term !== lastSearchTermRef.current) {
      lastSearchTermRef.current = term;

      searchAll(term, includeHistorical, true).then(success => {
        if (success) {
          setHasSearched(true);
        }
      });
    }
  }, [includeHistorical, searchAll]);

  // This function runs on every keystroke
  const handleInputChange = (e) => {
    const term = e.target.value;
    setSearchTerm(term);
    setIsTyping(true);

    // Clear any existing typing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    if (term === '') {
      // If search term is empty, clear results
      setHasSearched(false);
      lastSearchTermRef.current = '';
      setIsTyping(false);
    } else if (term.length >= 3) {
      // Set a timeout to execute search after user stops typing
      // This approach is more reliable than debounce for preventing 
      // intermediate searches
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        executeSearch(term);
      }, 1000); // 1-second delay after typing stops
    }
  };

  // Function to handle explicit search (button click or Enter)
  const handleSearch = () => {
    if (!searchTerm) return;

    // Cancel any pending timeouts
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    // Update the last search term and execute the search
    lastSearchTermRef.current = searchTerm;
    searchAll(searchTerm, includeHistorical, true).then(success => {
      if (success) {
        setHasSearched(true);
      }
    });
  };

  // Function to clear the search field
  const handleClearSearch = () => {
    setSearchTerm('');
    setHasSearched(false);
    // Focus on the search field after clearing
    if (searchFieldRef.current) {
      searchFieldRef.current.focus();
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Box sx={{ mb: 4 }}>
      <ToastContainer
        position="top-right"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
      />
      <Typography variant="h5" gutterBottom>
        CSV Search
      </Typography>

      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%', position: 'relative' }}>
            <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
              <TextField
                inputRef={searchFieldRef}
                label="Search Term"
                placeholder="Enter search term..."
                variant="outlined"
                fullWidth
                value={searchTerm}
                onChange={handleInputChange}
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
              <Button
                variant="outlined"
                color="secondary"
                onClick={handleClearSearch}
                startIcon={<ClearIcon />}
                sx={{ height: 56, ml: 1 }}
                disabled={searchLoading || !searchTerm}
              >
                Clear
              </Button>
            </Box>
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
            {hasSearched ? "Search Results" : "CSV File Preview"}
          </Typography>

          <Box sx={{ mb: 2 }}>
            <Alert
              severity={hasSearched ? (results?.success ? "success" : "info") : "info"}
              sx={{ mb: 2 }}
            >
              {hasSearched ? results?.message : (previewData?.message || "Showing first 100 entries from the CSV file")}
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
                <Table sx={{ width: 'auto', tableLayout: 'fixed' }} aria-label="data table">
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      {hasSearched && (
                        <TableCell>
                          <Typography variant="subtitle2">
                            <strong>#</strong>
                          </Typography>
                        </TableCell>
                      )}
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
                          <TableCell colSpan={results.headers.length + 1} align="center">
                            No data found
                          </TableCell>
                        </TableRow>
                      ) : Array.isArray(results.data) ? (
                        results.data.map((row, index) => (
                          <TableRow
                            key={index}
                            sx={{ '&:nth-of-type(odd)': { backgroundColor: '#fafafa' } }}
                          >
                            <TableCell>
                              {index + 1}
                            </TableCell>
                            {results.headers.map((header) => {
                              // Handle special formatting for specific columns
                              let cellContent = row[header];

                              // Format dates to ISO 8601 (YYYY-MM-DD)
                              if (header === "Creation Date" && cellContent) {
                                const date = new Date(cellContent);
                                cellContent = date.toISOString().split('T')[0];
                              }

                              return (
                            <TableCell key={`${index}-${header}`}>
                              {header === "File Name" ? (
                                <a 
                                  href={`http://localhost:8000/api/files/download/${cellContent}`} 
                                  download
                                  style={{ 
                                    color: 'inherit', 
                                    textDecoration: 'underline',
                                    cursor: 'pointer'
                                  }}
                                >
                                  {cellContent}
                                </a>
                              ) : (
                                cellContent
                              )}
                            </TableCell>
                              );
                            })}
                          </TableRow>
                        ))
                      ) : (
                        <TableRow>
                          <TableCell>
                            1
                          </TableCell>
                          {results.headers.map((header) => {
                            // Handle special formatting for specific columns
                            let cellContent = results.data[header];

                            // Format dates to ISO 8601 (YYYY-MM-DD) 
                            if (header === "Creation Date" && cellContent) {
                              const date = new Date(cellContent);
                              cellContent = date.toISOString().split('T')[0];
                            }

                            return (
                              <TableCell key={header}>
                                {header === "File Name" ? (
                                  <a 
                                    href={`http://localhost:8000/api/files/download/${cellContent}`} 
                                    download
                                    style={{ 
                                      color: 'inherit', 
                                      textDecoration: 'underline',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    {cellContent}
                                  </a>
                                ) : (
                                  cellContent
                                )}
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

                            // Format dates to ISO 8601 (YYYY-MM-DD)
                            if (header === "Creation Date" && cellContent) {
                              const date = new Date(cellContent);
                              cellContent = date.toISOString().split('T')[0];
                            }

                            return (
                              <TableCell key={`${index}-${header}`}>
                                {header === "File Name" ? (
                                  <a 
                                    href={`http://localhost:8000/api/files/download/${cellContent}`} 
                                    download
                                    style={{ 
                                      color: 'inherit', 
                                      textDecoration: 'underline',
                                      cursor: 'pointer'
                                    }}
                                  >
                                    {cellContent}
                                  </a>
                                ) : (
                                  cellContent
                                )}
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
