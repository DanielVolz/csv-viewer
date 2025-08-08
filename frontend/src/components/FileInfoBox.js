import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  CircularProgress,
  Avatar,
  Chip,
  Fade,
  IconButton,
  Paper,
  Tooltip
} from '@mui/material';
import {
  Refresh,
  Warning
} from '@mui/icons-material';
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
  const [idxStatus, setIdxStatus] = useState('idle');
  const [lastSuccess, setLastSuccess] = useState(null);
  const [progress, setProgress] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [justUpdated, setJustUpdated] = useState(false);

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
    if (lastSuccess) return `Index healthy · last success ${new Date(lastSuccess).toLocaleString()}`;
    return 'Index idle (no successful run yet)';
  };

  const fetchFileInfo = useCallback(async (isManualRefresh = false) => {
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
      // Only trigger global loading placeholder if we have no data yet (initial mount)
      if (!fileInfo) {
        setLoading(true);
      }

      const response = await axios.get('/api/files/netspeed_info', { signal: controller.signal });
      const data = response.data;

      if (data.success) {
        setFileInfo(data);
        setError(null);
        console.log('File info loaded:', data.date, 'Records:', data.line_count);
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
      if (!fileInfo) { // only end initial loading placeholder if we were in initial load
        setLoading(false);
      }
    }
  }, [fileInfo]); // depend on fileInfo to know if initial load done

  const handleRefresh = async () => {
    if (refreshing) return; // guard
    const start = Date.now();
    setRefreshing(true);
    setJustUpdated(false);
    await fetchFileInfo(true);
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
    // Only fetch file info once on component mount
    // File info will only update when component is remounted (e.g., page refresh)
    fetchFileInfo();

    // NO INTERVAL - File info is static until page refresh
    // The daily netspeed.csv is loaded at 7:00 AM, user can refresh page to see new data
  }, [fetchFileInfo]);

  // NOTE: We no longer early-return ONLY for refresh; only for true initial load (no fileInfo yet)
  if (loading && !fileInfo && !error && !missingFile) {
    return (
      <Fade in>
        <Card
          elevation={0}
          sx={{
            bgcolor: 'background.paper',
            backdropFilter: 'blur(20px)',
            border: 1,
            borderColor: 'divider',
            borderRadius: 4,
            p: 3,
            textAlign: 'center',
            opacity: 0.9,
            minHeight: 180 // keep some height baseline
          }}
        >
          <CircularProgress size={40} thickness={4} />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
            Loading file information...
          </Typography>
        </Card>
      </Fade>
    );
  }

  if (error) {
    return (
      <Card
        elevation={0}
        sx={{
          bgcolor: 'error.light',
          border: 1,
          borderColor: 'error.main',
          borderRadius: 4,
          opacity: 0.1
        }}
      >
        <CardContent sx={{ p: 3, textAlign: 'center' }}>
          <Avatar
            sx={{
              bgcolor: 'error.main',
              width: 48,
              height: 48,
              mx: 'auto',
              mb: 2
            }}
          >
            <Warning />
          </Avatar>
          <Typography variant="body2" color="error.main" gutterBottom>
            {error}
          </Typography>
          <IconButton
            onClick={handleRefresh}
            disabled={refreshing}
            sx={{
              mt: 1,
              bgcolor: 'error.light',
              '&:hover': {
                bgcolor: 'error.main',
              },
              opacity: 0.7
            }}
          >
            <Refresh />
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
          borderRadius: 4,
          opacity: 0.9,
          mb: 4
        }}
      >
        <CardContent sx={{ p: 3, textAlign: 'center' }}>
          <Avatar
            sx={{
              bgcolor: 'warning.main',
              width: 48,
              height: 48,
              mx: 'auto',
              mb: 2
            }}
          >
            <Warning />
          </Avatar>
          <Typography variant="subtitle1" fontWeight={600} gutterBottom>
            Kein aktuelles netspeed.csv gefunden
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Die Datei wurde nicht im Verzeichnis /app/data gefunden. Sobald sie erscheint, können Sie aktualisieren.
          </Typography>
          <IconButton
            onClick={handleRefresh}
            disabled={refreshing}
            size="small"
            sx={{
              bgcolor: 'warning.light',
              '&:hover': { bgcolor: 'warning.main' }
            }}
          >
            {refreshing ? <CircularProgress size={16} /> : <Refresh fontSize="small" />}
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
            Current File: <strong>netspeed.csv</strong> • Created: <strong>{fileInfo?.date ? new Date(fileInfo.date).toLocaleDateString() : '-'}</strong> • Records: <strong>{fileInfo?.line_count?.toLocaleString() || '0'}</strong>
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Tooltip title={indexStatusLabel()} arrow placement="top">
              <Chip
                label="Active"
                color="success"
                size="small"
                variant="outlined"
                sx={{ cursor: 'help' }}
              />
            </Tooltip>
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
        {/* Header */}
        <Box sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3
        }}>
          <Box sx={{ display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h6" fontWeight={600}>
              Current File Information
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5, minHeight: 18 }}>
              {refreshing && (
                <Typography variant="caption" color="info.main" sx={{ fontWeight: 500 }}>
                  Refreshing…
                </Typography>
              )}
              {!refreshing && justUpdated && (
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 500 }}>
                  Updated just now
                </Typography>
              )}
              {!refreshing && !justUpdated && lastUpdated && (
                <Typography variant="caption" color="text.secondary">
                  Updated {new Date(lastUpdated).toLocaleTimeString()}
                </Typography>
              )}
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Tooltip title={indexStatusLabel()} arrow placement="top">
              <Chip
                label="Active"
                color="success"
                size="small"
                variant="outlined"
                sx={{ cursor: 'help' }}
              />
            </Tooltip>
            <IconButton
              onClick={handleRefresh}
              disabled={refreshing}
              size="small"
            >
              {refreshing ? (
                <Refresh fontSize="small" sx={{
                  '@keyframes spin': { to: { transform: 'rotate(360deg)' } },
                  animation: 'spin 0.8s linear infinite'
                }} />
              ) : (
                <Refresh fontSize="small" />
              )}
            </IconButton>
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
          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              File Name
            </Typography>
            <Typography variant="body1" fontWeight={500}>
              netspeed.csv
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Created
            </Typography>
            <Typography variant="body1" fontWeight={500}>
              {fileInfo?.date || 'Unknown'}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Total Records
            </Typography>
            <Typography variant="body1" fontWeight={500}>
              {fileInfo?.line_count?.toLocaleString() || '0'}
            </Typography>
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              Status
            </Typography>
            <Typography variant="body1" fontWeight={500} color="success.main">
              Ready
            </Typography>
          </Box>
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