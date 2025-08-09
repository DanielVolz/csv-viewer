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
  Clear,
  Download
} from '@mui/icons-material';
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';
import DataTable from './DataTable';
import { toast } from 'react-toastify';

// Preview block extracted to reduce re-renders while typing
const PreviewSection = React.memo(function PreviewSection({ previewData, handleMacAddressClick, handleSwitchPortClick }) {
  if (!previewData || !previewData.data) return null;
  return (
    <Box>
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
      <Alert severity="info" sx={{ mb: 3 }}>
        {previewData?.message || "Showing latest entries from the CSV file"}
      </Alert>
      <DataTable
        headers={previewData.headers}
        data={previewData.data}
        showRowNumbers={false}
        onMacAddressClick={handleMacAddressClick}
        onSwitchPortClick={handleSwitchPortClick}
      />
    </Box>
  );
});

function CSVSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [includeHistorical, setIncludeHistorical] = useState(false); // default disabled
  const [hasSearched, setHasSearched] = useState(false);
  const searchFieldRef = useRef(null);

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

  const { previewData, loading: previewLoading, error: previewError } = useFilePreview();
  const missingPreview = !previewLoading && previewData && previewData.success === false && (previewData.message || '').toLowerCase().includes('not found');
  // Block only while actively loading initial preview OR when file definitely missing
  const searchBlocked = previewLoading || missingPreview; // rename conceptually: execution blocked, not input

  // Debug: detailed logging + transition tracking
  const prevRef = useRef({});
  useEffect(() => {
    const prev = prevRef.current;
    const current = {
      previewLoading,
      previewData_success: previewData?.success,
      previewData_message: previewData?.message,
      previewHasHeaders: Array.isArray(previewData?.headers),
      previewHeadersLen: Array.isArray(previewData?.headers) ? previewData.headers.length : null,
      previewRows: Array.isArray(previewData?.data) ? previewData.data.length : null,
      missingPreview,
      searchBlocked,
      previewError,
      searchTerm,
      hasSearched,
      searchLoading,
      timestamp: new Date().toISOString()
    };

    // Only print diff rather than full state spam (but keep full snapshot once)
    if (!prev.__initialized) {
      console.debug('[CSVSearch][init-state]', current);
    } else {
      const diff = {};
      Object.keys(current).forEach(k => {
        if (current[k] !== prev[k]) diff[k] = { prev: prev[k], next: current[k] };
      });
      if (Object.keys(diff).length > 0) {
        console.debug('[CSVSearch][state-diff]', diff);
      }
      if (prev.searchBlocked !== current.searchBlocked) {
        if (current.searchBlocked) {
          console.warn('[CSVSearch][transition] searchBlocked became TRUE', {
            reason: previewLoading ? 'previewLoading' : (missingPreview ? 'missingPreview' : 'unknown'),
            previewLoading,
            missingPreview,
            previewError,
            previewData_success: previewData?.success,
            previewData_message: previewData?.message
          });
        } else {
          console.info('[CSVSearch][transition] searchBlocked became FALSE');
        }
      }
    }
    prevRef.current = { ...current, __initialized: true };
  }, [previewLoading, previewData, missingPreview, searchBlocked, previewError, searchTerm, hasSearched, searchLoading]);

  useEffect(() => {
    console.debug('[CSVSearch] mounted');
  }, []);

  // No stuck timer needed anymore

  const typingTimeoutRef = useRef(null);
  const lastSearchTermRef = useRef('');
  const [isTyping, setIsTyping] = useState(false);

  const isMacLike = (v) => /[0-9A-Fa-f]{2}([:\-][0-9A-Fa-f]{2}){5}/.test(v) || /^[0-9A-Fa-f]{12}$/.test(v);
  const executeSearch = useCallback((term) => {
    if (searchBlocked) {
      console.debug('[CSVSearch][executeSearch] prevented (blocked)', { term, previewLoading, missingPreview });
      return;
    }
    if (term.length >= 3 && term !== lastSearchTermRef.current) {
      lastSearchTermRef.current = term;
      const hist = isMacLike(term) ? true : includeHistorical;
      searchAll(term, hist, true).then(success => {
        if (success) {
          setHasSearched(true);
        }
      });
    }
  }, [includeHistorical, searchAll, searchBlocked, previewLoading, missingPreview]);

  const handleMacAddressClick = useCallback((macAddress) => {
    setSearchTerm(macAddress);
    lastSearchTermRef.current = macAddress;
    searchAll(macAddress, true, true).then(success => { // always historical for MAC click
      if (success) setHasSearched(true);
    });
  }, [searchAll]);

  const handleSwitchPortClick = useCallback((switchPort) => {
    // Currently just copies to clipboard, but could trigger search
    // Implementation can be extended later if needed
  }, []);

  const handleInputChange = useCallback((e) => {
    const term = e.target.value;
    setSearchTerm(term);
    setIsTyping(true);
  console.debug('[CSVSearch][handleInputChange] value', { term });

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
    if (searchBlocked) {
      console.debug('[CSVSearch][handleSearch] prevented manual search (blocked)', {
        searchTerm,
        previewLoading,
        missingPreview
      });
      return;
    }
    if (!searchTerm) return;
  console.debug('[CSVSearch][handleSearch] initiating search', { term: searchTerm });
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    lastSearchTermRef.current = searchTerm;
    const hist = isMacLike(searchTerm) ? true : includeHistorical;
    searchAll(searchTerm, hist, true).then(success => {
      if (success) {
        setHasSearched(true);
        console.debug('[CSVSearch][handleSearch] search executed', { term: searchTerm });
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

  // Export full search results (allResults) to CSV
  const handleExportCsv = useCallback(() => {
    try {
      const headers = allResults?.headers;
      const rows = allResults?.data;
      if (!headers || !Array.isArray(headers) || !rows || !Array.isArray(rows) || rows.length === 0) {
        toast.info('Nothing to export');
        return;
      }

      // CSV escaping: wrap in quotes, double internal quotes
      const esc = (val) => {
        if (val === null || val === undefined) return '';
        let s = String(val);
        // normalize line breaks
        s = s.replace(/\r\n|\r|\n/g, '\n');
        if (/[",\n]/.test(s)) {
          s = '"' + s.replace(/"/g, '""') + '"';
        }
        return s;
      };

      const headerLine = headers.map(esc).join(',');
      const dataLines = rows.map((row) => headers.map(h => esc(row[h])).join(','));
      const csvContent = [headerLine, ...dataLines].join('\n');

      // Add BOM for Excel compatibility
      const blob = new Blob(["\ufeff" + csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const term = lastSearchTermRef.current || searchTerm || 'search';
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
      a.href = url;
      a.download = `search_export_${term}_${timestamp}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${rows.length} rows`);
    } catch (e) {
      console.error('Export CSV error', e);
      toast.error('Failed to export CSV');
    }
  }, [allResults, searchTerm]);

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
            // keep input enabled; execution will be blocked while preview loads
            disabled={missingPreview} // only hard-disable if file truly missing
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
            disabled={missingPreview}
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
                variant="outlined"
                onClick={handleExportCsv}
                startIcon={<Download />}
                disabled={!hasSearched || searchLoading || !allResults || !Array.isArray(allResults?.data) || allResults.data.length === 0}
              >
                Export CSV
              </Button>
              <Button
                variant="contained"
                onClick={handleSearch}
                disabled={searchBlocked || searchLoading || !searchTerm || searchTerm.length < 3}
                startIcon={searchLoading ? <CircularProgress size={20} /> : <Search />}
              >
                {searchLoading ? 'Searching...' : (searchBlocked ? 'Waiting...' : 'Search')}
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
            {searchLoading ? 'Searching...' : 'Loading preview...'}
          </Typography>
        </Box>
      )}

  {/* Long preview load hint removed with simplified logic */}

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
            <PreviewSection
              previewData={previewData}
              handleMacAddressClick={handleMacAddressClick}
              handleSwitchPortClick={handleSwitchPortClick}
            />
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
            sx={{ mb: 3, '& .MuiAlert-message': { width: '100%' } }}
          >
            {(() => {
              const base = results?.message || '';
              const took = typeof results?.took_ms === 'number' ? results.took_ms : null;
              if (!took && took !== 0) return base;
              if (took < 100) {
                return `${base} (${took} ms)`;
              }
              const secs = (took / 1000).toFixed(2);
              return `${base} (${secs} s)`;
            })()}
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