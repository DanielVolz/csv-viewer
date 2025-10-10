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
  Stack,
  Skeleton,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell
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
const PreviewSection = React.memo(function PreviewSection({ previewData, handleMacAddressClick, handleSwitchPortClick, loading }) {
  if (!previewData || !previewData.data) return null;

  // Show warning for fallback files, info for normal files
  const alertSeverity = previewData?.using_fallback ? "warning" : "info";
  const displayFileName = previewData?.actual_file_name || previewData?.file_name;

  return (
    <Box sx={{ position: 'relative', overflow: 'hidden' }}>
      <Alert severity={alertSeverity} sx={{ mb: 3 }}>
        {(previewData?.message || "Showing latest entries from the CSV file")}
        {displayFileName ? ` • ${displayFileName}` : ''}
      </Alert>
      <Box sx={{
        position: 'relative',
        opacity: loading ? 0.6 : 1,
        transition: 'opacity 0.3s ease'
      }}>
        <DataTable
          headers={previewData.headers}
          data={previewData.data}
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
      </Box>
      {/* Shimmer overlay during loading */}
      {loading && (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '200%',
            height: '100%',
            background: (theme) =>
              theme.palette.mode === 'dark'
                ? 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)'
                : 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.6) 50%, transparent 100%)',
            animation: 'shimmer 2s ease-in-out infinite',
            pointerEvents: 'none',
            zIndex: 10,
            '@keyframes shimmer': {
              '0%': { transform: 'translateX(0)' },
              '100%': { transform: 'translateX(50%)' }
            }
          }}
        />
      )}
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
  const sanitizeTimeoutRef = useRef(null);

  // Sanitize display value in the input: remove optional SEP/sep prefix and any non-hex separators
  function sanitizeForDisplay(v) {
    if (v == null) return '';
    let s = String(v);
    // strip optional Cisco SEP prefix (case-insensitive), with optional separator after it
    s = s.replace(/^sep[-_:]?/i, '');
    // remove all whitespace (spaces, tabs, NBSP, etc.)
    s = s.replace(/\s+/g, '');
    // remove common delimiters (':', '-', ';', '.') and any other non-hex characters
    s = s.replace(/[^0-9A-Fa-f]/g, '');
    // present as uppercase condensed hex for a "normal" MAC look
    return s.toUpperCase();
  }

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

  // Disable preview fetching when landing with a query (?q=...), to avoid extra load and race
  const [previewEnabled, setPreviewEnabled] = React.useState(true);
  React.useEffect(() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const q = params.get('q');
      if (q && typeof q === 'string' && q.trim() !== '') {
        setPreviewEnabled(false);
      }
    } catch { }
  }, []);
  const { previewData, loading: previewLoading, error: previewError } = useFilePreview({ enabled: previewEnabled });
  const missingPreview = !previewLoading && previewData && previewData.success === false && (previewData.message || '').toLowerCase().includes('not found');
  // Detect when current netspeed.csv exists but is empty (no rows)
  const currentFileEmpty = Boolean(
    previewData &&
    previewData.success &&
    previewData.data &&
    previewData.data.length === 0 &&
    // Empty data and file is indeed empty (not just a small limit)
    previewData.message &&
    // Check if this is the current file (not a historical one) - check if it's not a numbered backup
    ((previewData.actual_file_name && !previewData.actual_file_name.match(/\.csv\.[0-9]+/)) || (!previewData.actual_file_name && previewData.file_name === 'netspeed.csv'))
  );
  const currentEmpty = useRef(currentFileEmpty);
  currentEmpty.current = currentFileEmpty;
  // Block only while actively loading initial preview; allow searches even if file is missing
  const searchBlocked = previewLoading; // execution blocked only during preview loading

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

  useEffect(() => {
    mountedRef.current = true;
    try {
      const params = new URLSearchParams(window.location.search);
      const q = params.get('q');
      if (q && typeof q === 'string') {
        setSearchTerm(q);
        initialQueryRef.current = q;
        // Delayed sanitize for MAC-like inputs
        if (sanitizeTimeoutRef.current) clearTimeout(sanitizeTimeoutRef.current);
        sanitizeTimeoutRef.current = setTimeout(() => {
          if (!mountedRef.current) return;
          const macCan = normalizeMacInput(q);
          if (macCan) setSearchTerm(sanitizeForDisplay(q));
        }, 1000);
      }
    } catch { }
    return () => {
      mountedRef.current = false;
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      if (sanitizeTimeoutRef.current) {
        clearTimeout(sanitizeTimeoutRef.current);
      }
    };
  }, [normalizeMacInput]);

  // If there is an initial query (?q=...), trigger search once not blocked
  useEffect(() => {
    if (initialQueryRef.current && !searchBlocked) {
      const term = initialQueryRef.current;
      initialQueryRef.current = null; // one-shot
      const cleaned = stripAllWhitespace(term);
      lastSearchTermRef.current = cleaned;
      const macCanonical = normalizeMacInput(cleaned);
      // Force historical search if current file is missing or empty
      const hist = includeHistorical || missingPreview || currentEmpty.current;
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchBlocked, includeHistorical, missingPreview, recordMac, searchAll, normalizeMacInput, stripAllWhitespace]);

  const typingTimeoutRef = useRef(null);
  const lastSearchTermRef = useRef('');
  const [isTyping, setIsTyping] = useState(false);
  const [historyAnchor, setHistoryAnchor] = useState(null);
  const historyOpen = Boolean(historyAnchor);

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
    // Use raw term for display; only strip whitespace for search
    const cleaned = stripAllWhitespace(term);
    if (searchBlocked) {
      return;
    }
    if (cleaned.length >= 3 && cleaned !== lastSearchTermRef.current) {
      lastSearchTermRef.current = cleaned;
      const macCanonical = normalizeMacInput(cleaned);
      // Auto-include historical when current file is missing or empty
      const hist = includeHistorical || missingPreview || currentEmpty.current;
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [includeHistorical, searchAll, searchBlocked, missingPreview, recordMac, normalizeMacInput, getLocationForMac, stripAllWhitespace]);

  const handleMacAddressClick = useCallback((macAddress) => {
    const macCanonical = normalizeMacInput(macAddress) || macAddress;
    // Display without separators per requirement
    setSearchTerm(macCanonical);
    lastSearchTermRef.current = macCanonical;
    {
      const loc = getLocationForMac(macCanonical);
      recordMac(macCanonical, loc || undefined);
    }
    // Auto-include historical when current file is missing or empty
    const hist = includeHistorical || missingPreview || currentEmpty.current;
    searchAll(macCanonical, hist, true).then(success => {
      if (!mountedRef.current) return;
      if (success) {
        setHasSearched(true);
      }
    });
  }, [searchAll, recordMac, normalizeMacInput, getLocationForMac, includeHistorical, missingPreview]);

  const handleSwitchPortClick = useCallback((switchPort) => {
    // Currently just copies to clipboard, but could trigger search
    // Implementation can be extended later if needed
  }, []);

  const handleInputChange = useCallback((e) => {
    const term = e.target.value;
    // Show what the user typed immediately
    setSearchTerm(term);
    // Schedule a delayed sanitize only if the input is MAC-like
    if (sanitizeTimeoutRef.current) clearTimeout(sanitizeTimeoutRef.current);
    sanitizeTimeoutRef.current = setTimeout(() => {
      if (!mountedRef.current) return;
      const macCan = normalizeMacInput(term);
      if (macCan) {
        const displaySanitized = sanitizeForDisplay(term);
        if (displaySanitized !== searchTerm) setSearchTerm(displaySanitized);
      }
    }, 1000);
    setIsTyping(true);

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    const cleaned = stripAllWhitespace(term);
    if (cleaned === '') {
      setHasSearched(false);
      lastSearchTermRef.current = '';
      setIsTyping(false);
    } else if (cleaned.length >= 3) {
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
        executeSearch(term);
      }, 1000);
    }
  }, [executeSearch, normalizeMacInput, stripAllWhitespace, searchTerm]);

  const handleSearch = useCallback(() => {
    if (searchBlocked || !searchTerm) return;

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    setIsTyping(false);
    const cleaned = stripAllWhitespace(searchTerm);
    lastSearchTermRef.current = cleaned;
    const macCanonical = normalizeMacInput(cleaned);
    // Auto-include historical when current file is missing or empty
    const hist = includeHistorical || missingPreview || currentEmpty.current;
    if (macCanonical) {
      const loc = getLocationForMac(macCanonical);
      recordMac(macCanonical, loc || undefined);
    }
    // Use the input as-is for search; history stores canonical MAC
    searchAll(cleaned, hist, true).then(success => {
      if (!mountedRef.current) return;
      if (success) {
        setHasSearched(true);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchTerm, includeHistorical, searchAll, searchBlocked, recordMac, normalizeMacInput, getLocationForMac, missingPreview, stripAllWhitespace]);

  const handleClearSearch = useCallback(() => {
    setSearchTerm('');
    setHasSearched(false);
    setIsTyping(false);
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
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
            // keep input enabled; execution is blocked only while preview loads
            disabled={false}
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
                    <Tooltip title="MAC history" placement="top" arrow>
                      <span>
                        <IconButton
                          onClick={(e) => setHistoryAnchor(e.currentTarget)}
                          size="small"
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
                          // Auto-include historical when current file is missing or empty
                          const hist = includeHistorical || missingPreview || currentEmpty.current;
                          searchAll(item.mac, hist, true).then(success => {
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
          {(missingPreview || currentEmpty.current) && (
            <Alert severity="warning" sx={{ mt: -1 }}>
              {missingPreview
                ? 'Current file missing: results will be shown from historical netspeed.csv files.'
                : 'Current file has no data: results will be shown from historical netspeed.csv files.'}
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
                disabled={searchLoading || !searchTerm || searchTerm.length < 3}
                startIcon={
                  searchLoading ? (
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      <CircularProgress size={20} />
                    </Box>
                  ) : (
                    <Search />
                  )
                }
              >
                {searchLoading ? 'Searching...' : 'Search'}
              </Button>
            </Box>
          </Box>

        </Stack>
      </Paper>

      {/* Loading State - Show skeleton table for both search and preview */}
      {searchLoading && (
        <Box>
          {/* Search Results Header with skeleton */}
          <Box sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3
          }}>
            <Box>
              <Typography variant="h5" fontWeight={700}>
                Search Results
              </Typography>
            </Box>
          </Box>

          {/* Status Message with skeleton */}
          <Box sx={{ mb: 3 }}>
            <Skeleton variant="rectangular" width="100%" height={48} animation="wave" sx={{ borderRadius: 1 }} />
          </Box>

          <Paper
            elevation={1}
            sx={{
              p: 3,
              borderRadius: 2,
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            <Table>
              <TableHead>
                <TableRow>
                  {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                    <TableCell key={i}>
                      <Skeleton variant="text" width="100%" height={30} animation="wave" />
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {[1, 2, 3, 4, 5, 6, 7].map((row) => (
                  <TableRow key={row}>
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((col) => (
                      <TableCell key={col}>
                        <Skeleton variant="text" width="100%" height={20} animation="wave" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {/* Shimmer overlay */}
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: '-100%',
                width: '200%',
                height: '100%',
                background: (theme) =>
                  theme.palette.mode === 'dark'
                    ? 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)'
                    : 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.6) 50%, transparent 100%)',
                animation: 'shimmer 2s ease-in-out infinite',
                pointerEvents: 'none',
                zIndex: 10,
                '@keyframes shimmer': {
                  '0%': { transform: 'translateX(0)' },
                  '100%': { transform: 'translateX(50%)' }
                }
              }}
            />
          </Paper>
        </Box>
      )}

      {previewLoading && !previewData && (
        <Box>
          {/* Preview Alert with skeleton */}
          <Box sx={{ mb: 3 }}>
            <Skeleton variant="rectangular" width="100%" height={48} animation="wave" sx={{ borderRadius: 1 }} />
          </Box>

          <Paper
            elevation={1}
            sx={{
              p: 3,
              borderRadius: 2,
              position: 'relative',
              overflow: 'hidden'
            }}
          >
            <Table>
              <TableHead>
                <TableRow>
                  {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
                    <TableCell key={i}>
                      <Skeleton variant="text" width="100%" height={30} animation="wave" />
                    </TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {[1, 2, 3, 4, 5].map((row) => (
                  <TableRow key={row}>
                    {[1, 2, 3, 4, 5, 6, 7, 8].map((col) => (
                      <TableCell key={col}>
                        <Skeleton variant="text" width="100%" height={20} animation="wave" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {/* Shimmer overlay */}
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: '-100%',
                width: '200%',
                height: '100%',
                background: (theme) =>
                  theme.palette.mode === 'dark'
                    ? 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)'
                    : 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.6) 50%, transparent 100%)',
                animation: 'shimmer 2s ease-in-out infinite',
                pointerEvents: 'none',
                zIndex: 10,
                '@keyframes shimmer': {
                  '0%': { transform: 'translateX(0)' },
                  '100%': { transform: 'translateX(50%)' }
                }
              }}
            />
          </Paper>
        </Box>
      )}

      {/* Error State */}
      {(searchError || previewError) && (
        <Alert
          severity="error"
          sx={{ mb: 3 }}
        />
      )}

      {/* Error State - Preview Error */}
      {previewError && !hasSearched && !previewLoading && (
        <ErrorDisplay
          type="error"
          title="Preview-Fehler"
          message={previewError}
          variant="paper"
          sx={{ mb: 3 }}
        />
      )}

      {/* Welcome Message or Preview - Show when no search has been performed */}
      {!searchLoading && !previewLoading && !hasSearched && (
        <>
          {missingPreview ? (
            <ErrorDisplay
              type="warning"
              title="Keine netspeed.csv gefunden"
              message="Bitte legen Sie eine Datei im /app/data Verzeichnis ab und laden Sie die Seite neu. Die Suche wird auf historische Daten zurückgreifen."
              variant="paper"
            />
          ) : previewData && previewData.data ? (
            <PreviewSection
              previewData={previewData}
              handleMacAddressClick={handleMacAddressClick}
              handleSwitchPortClick={handleSwitchPortClick}
              loading={previewLoading}
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
              ignoreSettings={false} // Respect settings configuration
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