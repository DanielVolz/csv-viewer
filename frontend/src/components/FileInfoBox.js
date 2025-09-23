import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, Typography, Box, CircularProgress, IconButton, Skeleton, Paper, Tooltip, Chip } from '@mui/material';
import { Refresh, Warning, CheckCircleRounded } from '@mui/icons-material';
import axios from 'axios';
import { toast } from 'react-toastify';

const FileInfoBox = React.memo(({ compact = false }) => {
  const [fileInfo, setFileInfo] = useState(null);
  const [loading, setLoading] = useState(true); // true only for very first load; later refresh keeps layout
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const isFetchingRef = React.useRef(false);
  const [missingFile, setMissingFile] = useState(false);
  // Index status state (lightweight copy of logic from FileTable)
  const [idxStatus] = useState('idle');
  const [lastSuccess, setLastSuccess] = useState(null);
  const [progress] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [justUpdated, setJustUpdated] = useState(false);
  // Guards to prevent redundant work
  const didInitRef = React.useRef(false);
  const prevSigRef = React.useRef(null);

  const loadIndexState = useCallback(async () => {
    try {
      const r = await fetch('/api/files/index/status');
      if (!r.ok) return;
      const data = await r.json();
      const state = data?.state || {};
      const ls = state.last_success || state.last_run;
      if (ls) setLastSuccess(ls);
      // If there's an active task we don't have real-time here, just show healthy or idle
    } catch (_) { /* ignore */ }
  }, []);

  // Very small poll if we detect active indexing later (future extension)
  useEffect(() => { loadIndexState(); }, [loadIndexState]);

  const indexStatusLabel = () => {
    if (idxStatus === 'starting') return 'Index rebuild starting';
    if (idxStatus === 'running') return `Rebuilding index${progress?.total_files ? ` (${progress.index || 0}/${progress.total_files})` : ''}`;
    if (idxStatus === 'failed' || idxStatus === 'error') return 'Index rebuild error';
    if (lastSuccess) {
      try {
        const d = new Date(lastSuccess);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return `Index healthy · last success ${y}-${m}-${day} ${hh}:${mm}`;
      } catch {
        return `Index healthy`;
      }
    }
    return 'Index idle (no successful run yet)';
  };

  const fetchFileInfo = useCallback(async ({ initial = false } = {}) => {
    // Prevent multiple simultaneous requests
    if (isFetchingRef.current) {
      return;
    }
    // Controller & timeout flag need function scope (used in catch)
    let timedOut = false;
    const controller = new AbortController();
    const timeout = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, 12000);

    try {
      isFetchingRef.current = true;
      // Only show big placeholder on first load
      if (initial) setLoading(true);

      const response = await axios.get('/api/files/netspeed_info', { signal: controller.signal });
      const data = response.data;

      if (data.success) {
        setFileInfo(data);
        setError(null);
        // Log only when content actually changes
        try {
          const sig = `${data.date}|${data.line_count}`;
          if (sig !== prevSigRef.current) {
            prevSigRef.current = sig;
            console.info('File info loaded:', data.date, 'Records:', data.line_count);
          }
        } catch { }
        setMissingFile(false);
        setLastUpdated(Date.now());
      } else {
        // Treat missing file as a non-error (informational state)
        if ((data.message || '').toLowerCase().includes('not found')) {
          setMissingFile(true);
          setFileInfo({ date: null, line_count: 0, success: false });
          setError(null);
        } else {
          setError(data.message || 'Failed to fetch file information');
        }
      }
    } catch (err) {
      if (axios.isCancel(err) || err?.name === 'CanceledError') {
        if (timedOut) {
          setError('Timed out fetching file information');
        } else {
          // Silent cancellation (unmount / strict mode) -> do not set a user-facing error
          console.debug('File info request cancelled (ignored).');
        }
      } else {
        setError('Error fetching file information');
        console.error('Error fetching file info:', err);
      }
    } finally {
      clearTimeout(timeout);
      isFetchingRef.current = false;
      if (initial) setLoading(false);
    }
  }, []);

  const handleRefresh = async () => {
    if (refreshing) return; // guard
    const start = Date.now();
    setRefreshing(true);
    setJustUpdated(false);
    await fetchFileInfo({ initial: false });
    // Enforce minimal visible spinner time (600ms)
    const elapsed = Date.now() - start;
    const MIN_MS = 600;
    if (elapsed < MIN_MS) {
      await new Promise(r => setTimeout(r, MIN_MS - elapsed));
    }
    setRefreshing(false);
    setJustUpdated(true);
    setLastUpdated(Date.now());
    toast.success('File info refreshed', { autoClose: 1200, pauseOnHover: false });
    // clear flag after 2s
    setTimeout(() => setJustUpdated(false), 2000);
  };

  useEffect(() => {
    // Only fetch file info once on component mount (guard StrictMode double-invoke)
    if (didInitRef.current) return;
    didInitRef.current = true;
    fetchFileInfo({ initial: true });

    // NO INTERVAL - File info is static until page refresh
    // The daily netspeed.csv is loaded at 7:00 AM, user can refresh page to see new data
  }, [fetchFileInfo]);

  // NOTE: We no longer early-return ONLY for refresh; only for true initial load (no fileInfo yet)
  const initialLoading = loading && !fileInfo && !error && !missingFile;

  if (error) {
    return (
      <Card
        elevation={0}
        sx={{
          bgcolor: 'error.light',
          border: 1,
          borderColor: 'error.main',
          borderRadius: 2,
          opacity: 0.15,
          minHeight: 110,
          display: 'flex'
        }}
      >
        <CardContent sx={{ py: 1, px: 1.5, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', minHeight: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden', minWidth: 0 }}>
            <Warning sx={{ color: 'error.main', fontSize: 20 }} />
            <Typography variant="caption" color="error.main" noWrap>
              {error}
            </Typography>
          </Box>
          <IconButton
            onClick={handleRefresh}
            disabled={refreshing}
            size="small"
            sx={{ bgcolor: 'error.light', '&:hover': { bgcolor: 'error.main', color: 'error.contrastText' }, width: 30, height: 30 }}
          >
            {refreshing ? <CircularProgress size={16} /> : <Refresh fontSize="inherit" />}
          </IconButton>
        </CardContent>
      </Card>
    );
  }

  if (missingFile) {
    return (
      <Card
        elevation={0}
        sx={{
          bgcolor: 'background.paper',
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          opacity: 0.95,
          mb: 4,
          minHeight: 70,
          display: 'flex',
          alignItems: 'center'
        }}
      >
        <CardContent sx={{ py: 0, px: 1.5, flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between', minHeight: 70, '&:last-child': { pb: 0 } }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, overflow: 'hidden', minWidth: 0 }}>
            <Warning sx={{ color: 'warning.main', fontSize: 20 }} />
            <Typography variant="body1" color="text.secondary" noWrap>
              No netspeed.csv found — place a file in /app/data and refresh. The netspeed.csv should be created at 06:55 AM.
            </Typography>
          </Box>
          <IconButton
            onClick={handleRefresh}
            disabled={refreshing}
            size="small"
            sx={{ bgcolor: 'warning.light', '&:hover': { bgcolor: 'warning.main', color: 'warning.contrastText' }, width: 30, height: 30 }}
          >
            {refreshing ? <CircularProgress size={16} /> : <Refresh fontSize="inherit" />}
          </IconButton>
        </CardContent>
      </Card>
    );
  }

  if (compact) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 2,
          borderRadius: 1,
          border: '1px solid',
          borderColor: 'divider',
          background: 'background.paper'
        }}
      >
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 2
        }}>
          <Typography variant="body2" color="text.secondary">
            {(() => {
              const raw = fileInfo?.date || null; // Expecting YYYY-MM-DD from backend
              const today = new Date();
              const yyyy = today.getFullYear();
              const mm = String(today.getMonth() + 1).padStart(2, '0');
              const dd = String(today.getDate()).padStart(2, '0');
              const todayStr = `${yyyy}-${mm}-${dd}`;
              const isToday = raw === todayStr;
              // Prefer epoch mtime for local timezone; fallback to server time string or last_modified
              let timeStr = '';
              try {
                if (typeof fileInfo?.mtime === 'number') {
                  const d = new Date(fileInfo.mtime * 1000);
                  const hh = String(d.getHours()).padStart(2, '0');
                  const mi = String(d.getMinutes()).padStart(2, '0');
                  timeStr = `${hh}:${mi}`;
                } else if (fileInfo?.time) {
                  timeStr = String(fileInfo.time);
                } else if (fileInfo?.last_modified) {
                  const d = new Date(fileInfo.last_modified * 1000);
                  const hh = String(d.getHours()).padStart(2, '0');
                  const mi = String(d.getMinutes()).padStart(2, '0');
                  timeStr = `${hh}:${mi}`;
                }
              } catch { }
              const dateOut = raw ? (timeStr ? `${raw} ${timeStr}` : raw) : '-';
              const empty = typeof fileInfo?.line_count === 'number' && fileInfo.line_count <= 0;
              const fallbackUsing = Boolean(fileInfo?.using_fallback);
              return (
                <>
                  Current File: <strong>netspeed.csv</strong> • Created: <strong><Box component="span" sx={{ color: isToday ? 'success.main' : 'inherit' }}>{dateOut}</Box></strong> • Records: <strong>{fileInfo?.line_count?.toLocaleString() || '0'}</strong>
                  {empty && (
                    <Box component="span" sx={{ ml: 1, color: 'warning.main', fontWeight: 600 }}>
                      — Keine tagesaktuellen Daten vorhanden (aktuelles File ist leer)
                    </Box>
                  )}
                  {/* Removed verbose fallback text per request */}
                </>
              );
            })()}
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {(() => {
              const empty = typeof fileInfo?.line_count === 'number' && fileInfo.line_count <= 0;
              const fallbackUsing = Boolean(fileInfo?.using_fallback);
              if (empty || fallbackUsing) {
                return (
                  <Tooltip title={empty ? "No up-to-date data available (current file is empty). Searches will use historical files." : "Current file missing; using historical netspeed.csv.*"} arrow placement="top">
                    <Chip label={empty ? "No data today" : "Using historical"} color="warning" size="small" variant="filled" sx={{ cursor: 'help' }} icon={<Warning sx={{ fontSize: 18 }} />} />
                  </Tooltip>
                );
              }
              return (
                <Tooltip title={indexStatusLabel()} arrow placement="top">
                  <Chip label="Active" color="success" size="small" variant="filled" sx={{ cursor: 'help' }} icon={<CheckCircleRounded sx={{ fontSize: 18 }} />} />
                </Tooltip>
              );
            })()}
            <IconButton
              onClick={handleRefresh}
              disabled={refreshing}
              size="small"
            >
              {refreshing ? <CircularProgress size={16} /> : <Refresh fontSize="small" />}
            </IconButton>
          </Box>
        </Box>
      </Paper>
    );
  }

  return (
    <Card
      elevation={1}
      sx={{
        background: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        mb: 4,
        position: 'relative'
      }}
    >
      <CardContent sx={{ p: 3, transition: 'opacity 0.2s ease' }}>
        {/* Header / Skeleton */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
          <Box sx={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0 }}>
            {initialLoading ? (
              <>
                <Skeleton variant="text" width={200} height={28} />
                <Skeleton variant="text" width={160} height={18} />
              </>
            ) : (
              <>
                <Typography variant="h6" fontWeight={600}>Current File Information</Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, minHeight: 18 }}>
                  {refreshing && (
                    <Typography variant="caption" color="info.main" sx={{ fontWeight: 500 }}>Refreshing…</Typography>
                  )}
                  {!refreshing && justUpdated && (
                    <Typography variant="caption" color="success.main" sx={{ fontWeight: 500 }}>Updated just now</Typography>
                  )}
                  {!refreshing && !justUpdated && lastUpdated && (
                    <Typography variant="caption" color="text.secondary">Updated {new Date(lastUpdated).toLocaleTimeString()}</Typography>
                  )}
                </Box>
              </>
            )}
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            {initialLoading ? (
              <>
                <Skeleton variant="rounded" width={70} height={28} />
                <Skeleton variant="circular" width={32} height={32} />
              </>
            ) : (
              <>
                {(() => {
                  const empty = typeof fileInfo?.line_count === 'number' && fileInfo.line_count <= 0;
                  const fallbackUsing = Boolean(fileInfo?.using_fallback);
                  if (empty || fallbackUsing) {
                    return (
                      <Tooltip title={empty ? "No up-to-date data available (current file is empty). Searches will use historical files." : "Current file missing; using historical netspeed.csv.*"} arrow placement="top">
                        <Chip label={empty ? "No data today" : "Using historical"} color="warning" size="small" variant="filled" sx={{ cursor: 'help' }} icon={<Warning sx={{ fontSize: 18 }} />} />
                      </Tooltip>
                    );
                  }
                  return (
                    <Tooltip title={indexStatusLabel()} arrow placement="top">
                      <Chip label="Active" color="success" size="small" variant="filled" sx={{ cursor: 'help' }} icon={<CheckCircleRounded sx={{ fontSize: 18 }} />} />
                    </Tooltip>
                  );
                })()}
                <IconButton onClick={handleRefresh} disabled={refreshing} size="small">
                  {refreshing ? (
                    <Refresh fontSize="small" sx={{ '@keyframes spin': { to: { transform: 'rotate(360deg)' } }, animation: 'spin 0.8s linear infinite' }} />
                  ) : (
                    <Refresh fontSize="small" />
                  )}
                </IconButton>
              </>
            )}
          </Box>
        </Box>

        {/* Simple Stats Grid */}
        <Box sx={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: 2,
          opacity: refreshing ? 0.55 : 1,
          position: 'relative',
          '@keyframes pulseFade': {
            '0%': { backgroundColor: 'transparent' },
            '50%': { backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.04)' },
            '100%': { backgroundColor: 'transparent' }
          },
          animation: refreshing ? 'pulseFade 1.2s ease-in-out infinite' : 'none',
          borderRadius: 1
        }}>
          {['File Name', 'Created', 'Total Records', 'Status'].map((label, idx) => (
            <Box key={label}>
              <Typography variant="body2" color="text.secondary" gutterBottom>{label}</Typography>
              {initialLoading ? (
                <Skeleton variant="text" width={idx === 0 ? 120 : 90} height={24} />
              ) : (
                <Typography
                  variant="body1"
                  fontWeight={500}
                  color={
                    label === 'Status'
                      ? ((typeof fileInfo?.line_count === 'number' && fileInfo.line_count <= 0) || Boolean(fileInfo?.using_fallback) ? 'warning.main' : 'success.main')
                      : (label === 'Created' && (() => { try { const d = fileInfo?.date ? new Date(fileInfo.date) : null; const t = new Date(); return d && d.getFullYear() === t.getFullYear() && d.getMonth() === t.getMonth() && d.getDate() === t.getDate(); } catch { return false; } })())
                        ? 'success.main'
                        : 'inherit'
                  }
                >
                  {label === 'File Name' && 'netspeed.csv'}
                  {label === 'Created' && (() => {
                    const d = fileInfo?.date || '';
                    let t = '';
                    try {
                      if (typeof fileInfo?.mtime === 'number') {
                        const dt = new Date(fileInfo.mtime * 1000);
                        const hh = String(dt.getHours()).padStart(2, '0');
                        const mi = String(dt.getMinutes()).padStart(2, '0');
                        t = `${hh}:${mi}`;
                      } else if (fileInfo?.time) t = fileInfo.time;
                      else if (fileInfo?.last_modified) {
                        const dt = new Date(fileInfo.last_modified * 1000);
                        const hh = String(dt.getHours()).padStart(2, '0');
                        const mi = String(dt.getMinutes()).padStart(2, '0');
                        t = `${hh}:${mi}`;
                      }
                    } catch { }
                    return d ? `${d}${t ? ` ${t}` : ''}` : 'Unknown';
                  })()}
                  {label === 'Total Records' && (fileInfo?.line_count?.toLocaleString() || '0')}
                  {label === 'Status' && (
                    Boolean(fileInfo?.using_fallback)
                      ? 'Using historical'
                      : ((typeof fileInfo?.line_count === 'number' && fileInfo.line_count <= 0) ? 'Empty (using historical)' : 'Ready')
                  )}
                </Typography>
              )}
            </Box>
          ))}
        </Box>
        {/* Overlay spinner during refresh (non-blocking) */}
        {refreshing && (
          <Box sx={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            pointerEvents: 'none'
          }}>
            <CircularProgress size={36} thickness={4} />
          </Box>
        )}
      </CardContent>
    </Card>
  );
});

export default FileInfoBox;