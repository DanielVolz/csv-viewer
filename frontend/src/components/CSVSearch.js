import React, { useState, useCallback, useRef, useEffect } from 'react';
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
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';
import DataTable from './DataTable';

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
  const missingPreview = !previewLoading && previewData && previewData.success === false && (previewData.message || '').toLowerCase().includes('not found');
  const initializing = previewLoading && !previewData; // first-time load
  const searchBlocked = missingPreview || initializing; // block while initializing or missing file
  const [previewStuck, setPreviewStuck] = useState(false);

  useEffect(() => {
    let t;
    if (previewLoading) {
      t = setTimeout(() => setPreviewStuck(true), 16000);
    } else {
      setPreviewStuck(false);
    }
    return () => clearTimeout(t);
  }, [previewLoading]);

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

  const handleInputChange = useCallback((e) => {
    if (searchBlocked) return; // block typing logic from triggering searches
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
  }, [executeSearch]);

  const handleSearch = useCallback(() => {
    if (searchBlocked) return;
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
  }, [searchTerm, includeHistorical, searchAll, searchBlocked]);

  const handleClearSearch = useCallback(() => {
    setSearchTerm('');
    setHasSearched(false);
    if (searchFieldRef.current) {
      searchFieldRef.current.focus();
    }
  }, []);

  const handleKeyPress = useCallback((e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  }, [handleSearch]);

  return (
    <Box sx={{ mb: 4 }}>
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
          {/** Search Input */}
          <TextField
            inputRef={searchFieldRef}
            fullWidth
            variant="outlined"
            placeholder="Search for IP addresses, MAC addresses, hostnames, etc..."
            value={searchTerm}
            onChange={handleInputChange}
            onKeyPress={handleKeyPress}
            disabled={searchBlocked}
            sx={{
              '& .MuiOutlinedInput-root': {
                backgroundColor: 'background.paper',
                '&:hover': {
                  backgroundColor: 'background.default'
                },
                '&.Mui-focused': {
                  backgroundColor: 'background.default'
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
                        disabled={searchBlocked}
                      >
                        <Clear fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </InputAdornment>
              ),
            }}
          />
          {searchBlocked && (
            <Alert severity={missingPreview ? 'warning' : 'info'} sx={{ mt: -1 }}>
              {missingPreview
                ? 'Search disabled: netspeed.csv not available. Please provide the file and reload the page.'
                : 'Data preview is loading – Search temporarily disabled'}
            </Alert>
          )}

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
                    disabled={searchBlocked}
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
                disabled={searchBlocked || searchLoading || !searchTerm}
                startIcon={searchLoading ? <CircularProgress size={20} /> : <Search />}
              >
                {searchLoading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Box>

        </Stack>
      </Paper>

      {/* Loading State */}
      {(searchLoading || previewLoading) && !previewStuck && (
        <Box sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 2,
          py: 6
        }}>
          <CircularProgress size={32} />
          <Typography variant="body1" color="text.secondary">
            {searchLoading ? 'Searching...' : 'Loading preview...'}
          </Typography>
        </Box>
      )}

      {previewStuck && !previewError && (
        <Alert severity="warning" sx={{ mb: 3 }}>
          Preview loading is taking longer than expected. You can refresh the page or retry later.
        </Alert>
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

      {/* Welcome Message or Preview - Show when no search has been performed */}
      {!searchLoading && !previewLoading && !hasSearched && (
        <>
          {missingPreview ? (
            <Paper
              elevation={1}
              sx={{
                p: 4,
                textAlign: 'center',
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider'
              }}
            >
              <Typography variant="h6" gutterBottom>
                Keine netspeed.csv vorhanden
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Legen Sie eine Datei im Verzeichnis /app/data ab und aktualisieren Sie die Seite.
              </Typography>
            </Paper>
          ) : previewData && previewData.data ? (
            <Box>
              {/* Preview Header */}
              <Box sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 3
              }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Box>
                    <Typography variant="h5" fontWeight={700}>
                      Data Preview
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Latest entries from netspeed.csv
                    </Typography>
                  </Box>
                </Box>
              </Box>

              {/* Status Alert */}
              <Alert
                severity="info"
                sx={{ mb: 3 }}
              >
                {previewData?.message || "Showing latest entries from the CSV file"}
              </Alert>

              {/* Preview Data Table */}
              <DataTable
                headers={previewData.headers}
                data={previewData.data}
                showRowNumbers={false}
                onMacAddressClick={handleMacAddressClick}
                onSwitchPortClick={handleSwitchPortClick}
              />
            </Box>
          ) : (
            <Paper
              elevation={1}
              sx={{
                p: 4,
                textAlign: 'center',
                borderRadius: 2,
                border: '1px solid',
                borderColor: 'divider'
              }}
            >
              <Typography variant="h6" gutterBottom>
                Ready to Search
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Enter a search term above to find records in the CSV data.
                You can search for IP addresses, MAC addresses, switch ports, or any other data.
              </Typography>
            </Paper>
          )}
        </>
      )}

      {/* Results Section - Only show when user has searched */}
      {!searchLoading && hasSearched && results && (
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
                  Search Results
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {/* Results description */}
                </Typography>
              </Box>
            </Box>

          </Box>

          {/* Status Alert */}
          <Alert
            severity={results?.success ? "success" : "info"}
            sx={{ mb: 3 }}
          >
            {results?.message}
          </Alert>


          {/* Search Results Data Table */}
          {results?.data && results?.headers && (
            <DataTable
              headers={results.headers}
              data={results.data}
              showRowNumbers={true}
              onMacAddressClick={handleMacAddressClick}
              onSwitchPortClick={handleSwitchPortClick}
            />
          )}

          {/* Pagination Controls - moved to bottom */}
          {results?.success && results?.pagination && (
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

export default React.memo(CSVSearch);