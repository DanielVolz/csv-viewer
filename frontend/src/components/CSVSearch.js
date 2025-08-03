import React, { useState, useCallback, useRef } from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  Paper,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox,
  Pagination,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  InputAdornment,
  IconButton,
  Stack
} from '@mui/material';
import { 
  Search,
  Clear
} from '@mui/icons-material';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';
import DataTable from './DataTable';

function CSVSearch({ previewLimit }) {
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

  const { previewData, loading: previewLoading, error: previewError } = useFilePreview(previewLimit);

  const typingTimeoutRef = useRef(null);
  const lastSearchTermRef = useRef('');
  const [isTyping, setIsTyping] = useState(false);

  const executeSearch = useCallback((term) => {
    if (term.length >= 3 && term !== lastSearchTermRef.current) {
      lastSearchTermRef.current = term;
      searchAll(term, includeHistorical, true).then(success => {
        if (success) {
          setHasSearched(true);
        }
      });
    }
  }, [includeHistorical, searchAll]);

  const handleMacAddressClick = useCallback((macAddress) => {
    setSearchTerm(macAddress);
    lastSearchTermRef.current = macAddress;
    searchAll(macAddress, includeHistorical, true).then(success => {
      if (success) setHasSearched(true);
    });
  }, [includeHistorical, searchAll]);

  const handleSwitchPortClick = useCallback((switchPort) => {
    // Currently just copies to clipboard, but could trigger search
    // Implementation can be extended later if needed
  }, []);

  const handleInputChange = (e) => {
    const term = e.target.value;
    setSearchTerm(term);
    setIsTyping(true);

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    if (term === '') {
      setHasSearched(false);
      lastSearchTermRef.current = '';
      setIsTyping(false);
    } else if (term.length >= 3) {
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        executeSearch(term);
      }, 1000);
    }
  };

  const handleSearch = () => {
    if (!searchTerm) return;
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    lastSearchTermRef.current = searchTerm;
    searchAll(searchTerm, includeHistorical, true).then(success => {
      if (success) {
        setHasSearched(true);
      }
    });
  };

  const handleClearSearch = () => {
    setSearchTerm('');
    setHasSearched(false);
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
        position="top-center"
        autoClose={2000}
        hideProgressBar={true}
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss={false}
        draggable={false}
        pauseOnHover={false}
        limit={1}
        toastStyle={{
          background: theme => theme.palette.mode === 'dark' 
            ? '#1f2937' 
            : '#ffffff',
          border: theme => `1px solid ${theme.palette.mode === 'dark' 
            ? '#374151' 
            : '#e5e7eb'}`,
          borderRadius: '8px',
          color: theme => theme.palette.mode === 'dark' 
            ? '#f9fafb' 
            : '#1f2937',
          boxShadow: theme => theme.palette.mode === 'dark'
            ? '0 4px 6px -1px rgba(0, 0, 0, 0.3)'
            : '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
          fontSize: '14px',
          fontWeight: '500',
          minHeight: '48px',
          padding: '12px 16px'
        }}
      />

      {/* Search Section */}
      <Paper
        elevation={1}
        sx={{
          p: 3,
          mb: 4,
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider'
        }}
      >
        <Stack spacing={3}>
          {/* Search Input */}
          <TextField
            inputRef={searchFieldRef}
            fullWidth
            variant="outlined"
            placeholder="Search for IP addresses, MAC addresses, hostnames, etc..."
            value={searchTerm}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: theme => theme.palette.mode === 'dark' 
                  ? '#111827' 
                  : '#f8fafc',
                '&:hover': {
                  backgroundColor: theme => theme.palette.mode === 'dark' 
                    ? '#0f172a' 
                    : '#f1f5f9'
                },
                '&.Mui-focused': {
                  backgroundColor: theme => theme.palette.mode === 'dark' 
                    ? '#0f172a' 
                    : '#f1f5f9'
                }
              }
            }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Search />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    {isTyping && (
                      <CircularProgress size={20} />
                    )}
                    {searchTerm && (
                      <IconButton 
                        onClick={handleClearSearch}
                        size="small"
                      >
                        <Clear fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </InputAdornment>
              ),
            }}
          />

          {/* Action Bar */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: 2
          }}>
            {/* Left Side - Controls */}
            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
              <FormControlLabel
                control={
                  <Checkbox
                    checked={includeHistorical}
                    onChange={(e) => setIncludeHistorical(e.target.checked)}
                  />
                }
                label={
                  <Typography variant="body2" fontWeight={500}>
                    Include Historical Data
                  </Typography>
                }
              />
            </Box>

            {/* Right Side - Action Buttons */}
            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                onClick={handleSearch}
                disabled={searchLoading || !searchTerm}
                startIcon={searchLoading ? <CircularProgress size={20} /> : <Search />}
              >
                {searchLoading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Box>

        </Stack>
      </Paper>

      {/* Loading State */}
      {(searchLoading || previewLoading) && (
        <Box sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          alignItems: 'center', 
          gap: 2,
          py: 6
        }}>
          <CircularProgress size={32} />
          <Typography variant="body1" color="text.secondary">
            {searchLoading ? 'Searching...' : 'Loading...'}
          </Typography>
        </Box>
      )}

      {/* Error State */}
      {(searchError || previewError) && (
        <Alert 
          severity="error" 
          sx={{ mb: 3 }}
        >
          {searchError || previewError}
        </Alert>
      )}

      {/* Results Section */}
      {!searchLoading && !previewLoading && (hasSearched ? results : previewData) && (
        <Box>
            {/* Results Header */}
            <Box sx={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              mb: 3
            }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box>
                  <Typography variant="h5" fontWeight={700}>
                    {hasSearched ? "Search Results" : "Data Preview"}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {hasSearched 
                      ? ""
                      : "Latest entries from your CSV data"
                    }
                  </Typography>
                </Box>
              </Box>

            </Box>

            {/* Status Alert */}
            <Alert
              severity={hasSearched ? (results?.success ? "success" : "info") : "info"}
              sx={{ mb: 3 }}
            >
              {hasSearched ? results?.message : (previewData?.message || "Showing latest entries from the CSV file")}
            </Alert>


            {/* Unified Data Table */}
            {((hasSearched && results?.data && results?.headers) ||
              (!hasSearched && previewData?.data && previewData?.headers)) && (
                <DataTable
                  headers={hasSearched ? results.headers : previewData.headers}
                  data={hasSearched ? results.data : previewData.data}
                  showRowNumbers={hasSearched}
                  onMacAddressClick={handleMacAddressClick}
                  onSwitchPortClick={handleSwitchPortClick}
                />
              )}

              {/* Pagination Controls - moved to bottom */}
              {hasSearched && results?.success && results?.pagination && (
                <Paper
                  elevation={1}
                  sx={{
                    p: 2,
                    mt: 3,
                    borderRadius: 1,
                    border: '1px solid',
                    borderColor: 'divider'
                  }}
                >
                  <Box sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: 2
                  }}>
                    <Typography variant="body2" color="text.secondary">
                      Showing {results.pagination.currentStart} to {results.pagination.currentEnd} of {results.pagination.totalItems} results
                    </Typography>

                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <FormControl variant="outlined" size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>Page Size</InputLabel>
                        <Select
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
                        sx={{
                          '& .MuiPaginationItem-root': {
                            borderRadius: 2
                          }
                        }}
                      />
                    </Box>
                  </Box>
                </Paper>
              )}
            </Box>
      )}
    </Box>
  );
}

export default CSVSearch;