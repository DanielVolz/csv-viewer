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
  Chip,
  Button,
  Snackbar,
  Tooltip
} from '@mui/material';
import { Download, Replay, CheckCircleRounded, HistoryRounded, Inventory2Rounded } from '@mui/icons-material';
import axios from 'axios';
import useFiles from '../hooks/useFiles';
import useIndexingProgress from '../hooks/useIndexingProgress';
import IndexingProgress from './IndexingProgress';
import { useSettings } from '../contexts/SettingsContext';
import { toast } from 'react-toastify';

function FileTable() {
  const { files, loading, error, refetch } = useFiles();
  const { status: idxStatus, progress, result: idxResult, start: startProgress } = useIndexingProgress();
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState('');
  const [openSnackbar, setOpenSnackbar] = useState(false);
  // Last successful indexing timestamp (needs to be declared before any early return)
  const [lastSuccess, setLastSuccess] = useState(null);
  // Gate via local settings: only show rebuild UI if sshUsername === 'volzd'
  const { sshUsername } = useSettings();
  const isAdmin = sshUsername === 'volzd';

  // Update last success when indexing finishes successfully
  React.useEffect(() => {
    if (idxStatus === 'completed' && idxResult?.finished_at) {
      setLastSuccess(idxResult.finished_at);
    }
  }, [idxStatus, idxResult]);

  // On mount (or when lastSuccess missing), fetch persisted index state to restore last_success
  React.useEffect(() => {
    const f = (typeof window !== 'undefined' && typeof window.fetch === 'function')
      ? window.fetch
      : (typeof fetch === 'function' ? fetch : null);
    if (!f) return; // No fetch available (tests or SSR) – skip hydration
    const maybePromise = f('/api/files/index/status');
    if (!maybePromise || typeof maybePromise.then !== 'function') return; // Not a promise-like; skip
    maybePromise
      .then(r => (r && r.ok && typeof r.json === 'function' ? r.json() : null))
      .then(data => {
        const ts = data?.state?.last_success || data?.state?.last_run;
        if (ts && !lastSuccess) setLastSuccess(ts);
        // If backend reports an active running progress and hook idle -> hydrate
        if (data?.active && data.active.status === 'running' && idxStatus === 'idle') {
          startProgress(data.active.task_id || 'unknown', data.active);
        }
      })
      .catch(() => {/* ignore */ });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRebuild = async () => {
    setReindexing(true);
    try {
      const response = await axios.post('/api/search/index/rebuild');
      setReindexMessage(response.data.message || 'Rebuild started');
      setOpenSnackbar(true);
      if (response.data.task_id) startProgress(response.data.task_id);
      setTimeout(() => refetch(), 3000);
    } catch (error) {
      setReindexMessage('Error rebuilding: ' + (error.response?.data?.detail || error.message));
      setOpenSnackbar(true);
    } finally {
      setReindexing(false);
    }
  };

  // removed unused formatFileSize helper

  const getFileStatus = (file) => {
    if (file.name === 'netspeed.csv') {
      return { label: 'Active', color: 'success', icon: <CheckCircleRounded sx={{ fontSize: 18 }} /> };
    } else if (file.name.includes('_bak')) {
      return { label: 'Backup', color: 'warning', icon: <Inventory2Rounded sx={{ fontSize: 18 }} /> };
    } else {
      // Make 'Historical' subtly orange so it’s clearly not current
      return { label: 'Historical', color: 'warning', icon: <HistoryRounded sx={{ fontSize: 18 }} /> };
    }
  };

  // We avoid early returns so hook order stays stable across renders

  const statusColor = (s) => {
    if (s === 'running' || s === 'starting') return '#ffb300'; // amber (active)
    if (s === 'failed' || s === 'error') return '#d32f2f'; // red (error)
    if (lastSuccess) return '#2e7d32'; // green after any successful run
    return '#9e9e9e'; // idle (no successful run yet)
  };

  const statusLabel = (s) => {
    if (s === 'starting') return 'Index rebuild starting';
    if (s === 'running') return `Rebuilding index (${progress?.index || 0}/${progress?.total_files || 0})`;
    if (s === 'failed' || s === 'error') return 'Index rebuild error';
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
        return 'Index healthy';
      }
    }
    return 'Index idle (no successful run yet)';
  };

  // Robust download like in Search table: fetch blob, then save
  const makeHandleDownload = React.useCallback((filename) => async (e) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const resp = await fetch(`/api/files/download/${encodeURIComponent(filename)}`, {
        method: 'GET',
        headers: { 'Accept': 'text/csv' }
      });
      if (!resp.ok) {
        const text = await resp.text().catch(() => '');
        console.error('Download error response:', resp.status, text);
        toast.error(`Download failed (${resp.status})`);
        return;
      }
      const blob = await resp.blob();
      if (!blob || blob.size === 0) {
        toast.error('Empty file');
        return;
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Downloaded ${filename}`, { autoClose: 1200, pauseOnHover: false });
    } catch (err) {
      console.error('Download exception', err);
      toast.error('Download error');
    }
  }, []);


  return (
    <Box>
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress />
        </Box>
      )}
      {error && !loading && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}
      {!loading && !error && (
        <>
          <Snackbar
            open={openSnackbar}
            autoHideDuration={6000}
            onClose={() => setOpenSnackbar(false)}
            message={reindexMessage}
          />

          {/* Header Section */}
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography variant="h6" fontWeight={600}>Files</Typography>
              {isAdmin && (
                <Tooltip title={statusLabel(idxStatus)}>
                  <Box sx={{
                    width: 14,
                    height: 14,
                    borderRadius: '50%',
                    bgcolor: statusColor(idxStatus),
                    boxShadow: '0 0 4px rgba(0,0,0,0.25)',
                    border: '1px solid rgba(255,255,255,0.4)',
                    transition: 'background-color 0.3s'
                  }} />
                </Tooltip>
              )}
            </Box>
            {isAdmin && (
              <Button
                variant="contained"
                onClick={handleRebuild}
                disabled={reindexing || idxStatus === 'running' || idxStatus === 'starting'}
                startIcon={reindexing ? <CircularProgress size={18} /> : <Replay />}
                size="small"
              >
                {reindexing || idxStatus === 'running' || idxStatus === 'starting' ? 'Rebuilding…' : 'Rebuild Index'}
              </Button>
            )}
          </Box>
          {isAdmin && <IndexingProgress status={idxStatus} progress={progress} result={idxResult} />}

          {/* File Table */}
          <TableContainer component={Paper} elevation={1}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>File Name</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Created</TableCell>
                  <TableCell>Records</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {files && files.length > 0 ? (
                  files.map((file, index) => {
                    const status = getFileStatus(file);
                    const isActiveFile = file.name === 'netspeed.csv';
                    const indexStatusText = statusLabel(idxStatus);
                    return (
                      <TableRow key={index} hover>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          <Typography
                            variant="body2"
                            fontWeight={500}
                            component="a"
                            href={`/api/files/download/${encodeURIComponent(file.name)}`}
                            onClick={makeHandleDownload(file.name)}
                            sx={{
                              textDecoration: 'underline',
                              color: 'primary.main',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 0.5,
                              '&:hover': {
                                color: 'primary.dark'
                              }
                            }}
                          >
                            <Download fontSize="small" />
                            {file.name}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          {isActiveFile ? (
                            <Tooltip title={indexStatusText} placement="top" arrow>
                              <Chip
                                label={status.label}
                                color={status.color}
                                size="small"
                                variant="filled"
                                sx={{ cursor: 'help' }}
                                icon={status.icon}
                              />
                            </Tooltip>
                          ) : (
                            <Chip
                              label={status.label}
                              color={status.color}
                              size="small"
                              variant="filled"
                              icon={status.icon}
                            />
                          )}
                        </TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          <Typography variant="body2">
                            {(() => {
                              const datePart = file?.date ? String(file.date).slice(0, 10) : '';
                              let timePart = '';
                              try {
                                if (typeof file?.mtime === 'number') {
                                  const d = new Date(file.mtime * 1000);
                                  const hh = String(d.getHours()).padStart(2, '0');
                                  const mi = String(d.getMinutes()).padStart(2, '0');
                                  timePart = `${hh}:${mi}`;
                                } else if (file?.time) {
                                  // Fallback to legacy server-formatted time if mtime not available
                                  timePart = String(file.time);
                                }
                              } catch { }
                              const out = datePart ? `${datePart}${timePart ? ` ${timePart}` : ''}` : '-';
                              return out;
                            })()}
                          </Typography>
                        </TableCell>
                        <TableCell sx={{ whiteSpace: "nowrap" }}>
                          <Typography variant="body2">
                            {file.line_count ? file.line_count.toLocaleString() : '-'}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={4} align="center">
                      <Box sx={{ py: 3 }}>
                        <Typography variant="body2" color="text.secondary">
                          No files found
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </>
      )}
    </Box>
  );
}

export default FileTable;