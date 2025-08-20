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
  Download,
  History,
  ContentCopy,
  DeleteOutline
} from '@mui/icons-material';
import useSearchCSV from '../hooks/useSearchCSV';
import useFilePreview from '../hooks/useFilePreview';
import DataTable from './DataTable';
import { toast } from 'react-toastify';
import useMacHistory from '../hooks/useMacHistory';
import { Popover, List, ListItemButton, ListItemText, Tooltip } from '@mui/material';

// Preview block extracted to reduce re-renders while typing
const PreviewSection = React.memo(function PreviewSection({ previewData, handleMacAddressClick, handleSwitchPortClick }) {
  if (!previewData || !previewData.data) return null;
  return (
    <Box>
      <Alert severity="info" sx={{ mb: 3 }}>
        {(previewData?.message || "Showing latest entries from the CSV file")}
        {previewData?.file_name ? ` • ${previewData.file_name}` : ''}
      </Alert>
      <DataTable
        headers={previewData.headers}
        data={previewData.data}
        showRowNumbers={false}
        onMacAddressClick={handleMacAddressClick}
        onSwitchPortClick={handleSwitchPortClick}
        labelMap={{
          'Creation Date': 'Date',
          'IP Address': 'IP Addr.',
          'Voice VLAN': 'V-VLAN',
          'Serial Number': 'Serial',
          'Model Name': 'Model'
        }}
      />
    </Box>
  );
});

function CSVSearch() {
  const [searchTerm, setSearchTerm] = useState('');
  const [includeHistorical, setIncludeHistorical] = useState(false); // default disabled
  const [hasSearched, setHasSearched] = useState(false);
  const searchFieldRef = useRef(null);
  const initialQueryRef = useRef(null);
  const mountedRef = useRef(true);

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

  // Declare MAC history early to avoid TDZ when used in effects below
  const { list: macHistory, record: recordMac, remove: removeMac, update: updateMac } = useMacHistory();

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
    mountedRef.current = true;
    try {
      const params = new URLSearchParams(window.location.search);
      const q = params.get('q');
      if (q && typeof q === 'string') {
        setSearchTerm(q);
        initialQueryRef.current = q;
        console.debug('[CSVSearch] initial query param detected', { q });
      }
    } catch { }
    return () => {
      mountedRef.current = false;
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, []);

  // Remove all whitespace characters from a value
  const stripAllWhitespace = useCallback((v) => String(v ?? '').replace(/\s+/g, ''), []);

  // Normalize input MACs (handles optional SEP/sep prefix) to canonical condensed 12-hex (uppercase), e.g., AABBCCDDEEFF
  const normalizeMacInput = useCallback((v) => {
    if (!v) return null;
    let s = stripAllWhitespace(String(v));
    // strip optional Cisco SEP prefix (case-insensitive), with optional separator after it
    s = s.replace(/^sep[-_:]?/i, '');
    const hex = s.replace(/[^0-9A-Fa-f]/g, '');
    if (hex.length !== 12) return null;
    return hex.toUpperCase();
  }, [stripAllWhitespace]);

  // If there is an initial query (?q=...), trigger search once not blocked
  useEffect(() => {
    if (initialQueryRef.current && !searchBlocked) {
      const term = initialQueryRef.current;
      initialQueryRef.current = null; // one-shot
      const cleaned = stripAllWhitespace(term);
      lastSearchTermRef.current = cleaned;
      const macCanonical = normalizeMacInput(cleaned);
      const hist = macCanonical ? true : includeHistorical;
      if (macCanonical) recordMac(macCanonical);
      searchAll(cleaned, hist, true).then(success => {
        if (!mountedRef.current) return;
        if (success) setHasSearched(true);
        // After using the initial query once, clean the URL to remove ?q
        try {
          const cleanPath = window.location.pathname || '/';
          window.history.replaceState(null, '', cleanPath);
        } catch { }
      });
    }
  }, [searchBlocked, includeHistorical, recordMac, searchAll, normalizeMacInput, stripAllWhitespace]);

  // No stuck timer needed anymore

  const typingTimeoutRef = useRef(null);
  const lastSearchTermRef = useRef('');
  const [isTyping, setIsTyping] = useState(false);
  const [historyAnchor, setHistoryAnchor] = useState(null);
  const historyOpen = Boolean(historyAnchor);



  // Removed unused isMacLike helper to satisfy lint

  // Derive 5-char location (ABC01) from a row's Switch Hostname; exclude ABWRT
  const deriveLocationFromRow = useCallback((row) => {
    try {
      const host = (row?.['Switch Hostname'] || '').toString();
      const m = /([A-Za-z]{3}\d{2})/.exec(host);
      if (!m) return null;
      const code = m[1].toUpperCase();
      if (code === 'ABWRT') return null;
      return code;
    } catch { return null; }
  }, []);

  // Inspect latest results to map a MAC to a location code
  const getLocationForMac = useCallback((macCanonical) => {
    try {
      const rows = allResults?.data || results?.data || [];
      if (!Array.isArray(rows) || rows.length === 0) return null;
      const macLower = String(macCanonical).toLowerCase();
      const row = rows.find(r => {
        const m1 = (r['MAC Address'] || '').toString().replace(/[^0-9a-fA-F]/g, '').toLowerCase();
        const m2 = (r['MAC Address 2'] || '').toString().replace(/[^0-9a-fA-F]/g, '').toLowerCase();
        return m1 === macLower || m2 === macLower;
      });
      return deriveLocationFromRow(row);
    } catch { return null; }
  }, [allResults, results, deriveLocationFromRow]);

  // Backfill location for all history entries when we have results
  useEffect(() => {
    try {
      if (!Array.isArray(macHistory) || macHistory.length === 0) return;
      macHistory.forEach(item => {
        if (!item?.loc && item?.mac) {
          const macCan = normalizeMacInput(item.mac) || item.mac;
          const loc = getLocationForMac(macCan);
          if (loc) updateMac(item.mac, { loc });
        }
      });
    } catch { }
  }, [macHistory, results, allResults, updateMac, normalizeMacInput, getLocationForMac]);
  const executeSearch = useCallback((term) => {
    const cleaned = stripAllWhitespace(term);
    if (searchBlocked) {
      console.debug('[CSVSearch][executeSearch] prevented (blocked)', { term, previewLoading, missingPreview });
      return;
    }
    if (cleaned.length >= 3 && cleaned !== lastSearchTermRef.current) {
      if (cleaned !== term) setSearchTerm(cleaned);
      lastSearchTermRef.current = cleaned;
      const macCanonical = normalizeMacInput(cleaned);
      const hist = macCanonical ? true : includeHistorical;
      if (macCanonical) {
        const loc = getLocationForMac(macCanonical);
        recordMac(macCanonical, loc || undefined);
      }
      // Keep the user's typed term for search to maximize matches
      searchAll(cleaned, hist, true).then(success => {
        if (!mountedRef.current) return;
        if (success) {
          setHasSearched(true);
        }
      });
    }
  }, [includeHistorical, searchAll, searchBlocked, previewLoading, missingPreview, recordMac, normalizeMacInput, getLocationForMac, stripAllWhitespace]);

  const handleMacAddressClick = useCallback((macAddress) => {
    const macCanonical = normalizeMacInput(macAddress) || macAddress;
    // Display without separators per requirement
    setSearchTerm(macCanonical);
    lastSearchTermRef.current = macCanonical;
    {
      const loc = getLocationForMac(macCanonical);
      recordMac(macCanonical, loc || undefined);
    }
    // Use the displayed condensed MAC for searching as well
    searchAll(macCanonical, true, true).then(success => { // always historical for MAC click
      if (!mountedRef.current) return;
      if (success) {
        setHasSearched(true);
      }
    });
  }, [searchAll, recordMac, normalizeMacInput, getLocationForMac]);

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
    const cleaned = stripAllWhitespace(searchTerm);
    if (cleaned !== searchTerm) setSearchTerm(cleaned);
    lastSearchTermRef.current = cleaned;
    const macCanonical = normalizeMacInput(cleaned);
    const hist = macCanonical ? true : includeHistorical;
    if (macCanonical) {
      const loc = getLocationForMac(macCanonical);
      recordMac(macCanonical, loc || undefined);
    }
    // Use the input as-is for search; history stores canonical MAC
    searchAll(cleaned, hist, true).then(success => {
      if (!mountedRef.current) return;
      if (success) {
        setHasSearched(true);
        console.debug('[CSVSearch][handleSearch] search executed', { term: cleaned });
      }
    });
  }, [searchTerm, includeHistorical, searchAll, searchBlocked, recordMac, normalizeMacInput, getLocationForMac, previewLoading, missingPreview, stripAllWhitespace]);

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
                    <Tooltip title="MAC history" placement="top" arrow>
                      <span>
                        <IconButton
                          onClick={(e) => setHistoryAnchor(e.currentTarget)}
                          size="small"
                          disabled={missingPreview}
                          sx={{ opacity: 0.55, transition: 'opacity 0.2s', '&:hover': { opacity: 1 } }}
                          aria-label="open mac history"
                        >
                          <History fontSize="small" />
                        </IconButton>
                      </span>
                    </Tooltip>
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

          {/* MAC History Popover */}
          <Popover
            open={historyOpen}
            anchorEl={historyAnchor}
            onClose={() => setHistoryAnchor(null)}
            anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
            transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            PaperProps={{ sx: { width: 360 } }}
          >
            <Box sx={{ maxHeight: 300, overflowY: 'auto' }}>
              {(!macHistory || macHistory.length === 0) ? (
                <Box sx={{ p: 2 }}>
                  <Typography variant="body2" color="text.secondary">No MAC searches yet.</Typography>
                </Box>
              ) : (
                <List dense disablePadding>
                  {macHistory.map((item, idx) => {
                    const macCan = normalizeMacInput(item.mac) || item.mac;
                    const displayLoc = (item.loc || getLocationForMac(macCan) || '').toString();
                    return (
                      <ListItemButton
                        key={`${item.mac}-${idx}`}
                        onClick={() => {
                          setHistoryAnchor(null);
                          setSearchTerm(item.mac);
                          lastSearchTermRef.current = item.mac;
                          recordMac(item.mac, displayLoc || undefined);
                          searchAll(item.mac, true, true).then(success => {
                            if (!mountedRef.current) return;
                            if (success) {
                              setHasSearched(true);
                            }
                          });
                        }}
                        sx={{ py: 1, minHeight: 44 }}
                      >
                        <ListItemText
                          primary={item.mac}
                          secondary={(displayLoc ? `${displayLoc} · ` : '') + (item.lastSearchedAt ? (() => { const d = new Date(item.lastSearchedAt); const y = d.getFullYear(); const m = String(d.getMonth() + 1).padStart(2, '0'); const dd = String(d.getDate()).padStart(2, '0'); const hh = String(d.getHours()).padStart(2, '0'); const mi = String(d.getMinutes()).padStart(2, '0'); return `${y}-${m}-${dd} ${hh}:${mi}`; })() : '')}
                          primaryTypographyProps={{
                            variant: 'body1',
                            sx: {
                              lineHeight: 1.2,
                              fontSize: '0.98rem',
                              color: (theme) => theme.palette.mode === 'dark' ? theme.palette.common.white : theme.palette.text.primary
                            }
                          }}
                          secondaryTypographyProps={{
                            variant: 'body2',
                            sx: {
                              fontSize: '0.82rem',
                              color: (theme) => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.6)' : theme.palette.text.secondary
                            }
                          }}
                        />
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <Tooltip title="Copy" arrow>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard?.writeText(item.mac).then(() => toast.success('Copied MAC'));
                              }}
                            >
                              <ContentCopy sx={{ fontSize: 18 }} />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title="Remove" arrow>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                removeMac(item.mac);
                              }}
                            >
                              <DeleteOutline sx={{ fontSize: 18 }} />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      </ListItemButton>
                    );
                  })}
                </List>
              )}
            </Box>
          </Popover>
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
                No netspeed.csv found
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Place a file in the /app/data directory and refresh the page.
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
              labelMap={{
                'Creation Date': 'Date',
                'IP Address': 'IP Addr.',
                'Voice VLAN': 'V-VLAN',
                'Serial Number': 'Serial',
                'Model Name': 'Model'
              }}
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