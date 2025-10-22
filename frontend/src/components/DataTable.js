import React from 'react';
// Prefer real PNG logo; fallback to SVG if needed
import kemIconPng from '../assets/kem/kem_logo.png';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Tooltip,
  TableSortLabel,
  alpha
} from '@mui/material';
import { Download, Terminal } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { useSettings } from '../contexts/SettingsContext';

// Use only the PNG logo (removed SVG fallback to avoid missing module build error)
const kemIcon = kemIconPng;

/**
 * Unified DataTable component for preview and search results
 * Eliminates duplication and ensures consistent presentation
 */
function DataTable({
  headers,
  data,
  showRowNumbers = false,
  onMacAddressClick,
  onSwitchPortClick,
  labelMap,
  ignoreSettings = false // New prop to bypass settings filter for search results
}) {
  const { columns, sshUsername, navigateToSettings } = useSettings();

  // Preferred minimum widths per canonical header id to avoid wrapping
  const headerWidthMap = React.useMemo(() => ({
    '#': 48,
    'File Name': 160,
    'MAC Address': 170,
    'IP Address': 120,
    'Creation Date': 110,
    'Voice VLAN': 72,
    'Switch Hostname': 180,
    'Switch Port': 140,
    'Serial Number': 100,
    'Model Name': 85,
    'Line Number': 110,
  }), []);

  // Sorting state
  const [orderBy, setOrderBy] = React.useState(null); // header name
  const [order, setOrder] = React.useState('asc'); // 'asc' | 'desc'

  const handleSort = (header) => {
    if (orderBy === header) {
      setOrder(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setOrderBy(header);
      setOrder('asc');
    }
  };

  // Unified toast helper for consistent copy notifications
  const showCopyToast = (label, value, opts = {}) => {
    const display = typeof value === 'string' && value.length > 120 ? value.slice(0, 117) + '…' : value;
    toast.success(`📋 ${label}: ${display}`, {
      autoClose: 1000,
      pauseOnHover: false,
      pauseOnFocusLoss: false,
      ...opts
    });
  };

  // Get custom column configuration from settings
  const filteredHeaders = React.useMemo(() => {
    // If ignoreSettings is true, show all headers in original order
    if (ignoreSettings) {
      return Array.isArray(headers) ? headers.filter(h => h !== '#') : [];
    }

    // Use settings configuration
    if (Array.isArray(columns) && columns.length > 0) {
      // Get enabled columns in Settings order (respects user drag & drop)
      const headersSet = new Set(Array.isArray(headers) ? headers : []);
      const filtered = columns
        .filter(c => c.enabled && headersSet.has(c.id) && c.id !== '#')
        .map(c => c.id);

      // Debug log to help diagnose settings issues
      console.debug('[DataTable] Filtering headers:', {
        totalColumns: columns.length,
        enabledColumns: columns.filter(c => c.enabled).length,
        headersFromBackend: headers?.length || 0,
        filteredHeaders: filtered.length,
        missingInBackend: columns.filter(c => c.enabled && !headersSet.has(c.id)).map(c => c.id)
      });

      return filtered;
    }

    // Fallback: if columns not loaded yet, allow all provided headers
    return Array.isArray(headers) ? headers.filter(h => h !== '#') : [];
  }, [columns, headers, ignoreSettings]);

  // Utility used by sorting and UI: ensure defined before usage


  // Helpers for sorting
  const toIpKey = (ip) => {
    if (!ip || typeof ip !== 'string') return [];
    const parts = ip.split('.').map(p => parseInt(p, 10));
    if (parts.length === 4 && parts.every(n => Number.isFinite(n))) return parts;
    return [ip.toString()];
  };

  const toDateKey = (v) => {
    const t = Date.parse(v);
    return Number.isFinite(t) ? t : 0;
  };

  const toNumberKey = (v) => {
    if (v == null) return Number.NEGATIVE_INFINITY;
    const m = String(v).match(/\d+/);
    return m ? parseInt(m[0], 10) : Number.NEGATIVE_INFINITY;
  };

  const toMacKey = (v) => {
    if (!v) return '';
    return String(v).replace(/[^0-9a-fA-F]/g, '').toLowerCase();
  };

  const getKey = React.useCallback((header, value) => {
    // Define port sort key locally to avoid unstable dependency on an outer function
    const toPortKeyLocal = (v) => {
      if (!v || typeof v !== 'string') return [0];
      const s = convertToCiscoFormat(v) || String(v);
      const typeWeight = /^Gig\b/.test(s) ? 2 : /^Fas\b/.test(s) ? 1 : 0;
      const nums = s.match(/\d+/g) || [];
      const parts = nums.map(n => parseInt(n, 10));
      return [typeWeight, ...parts];
    };
    switch (header) {
      case 'IP Address':
        return toIpKey(value);
      case 'Creation Date':
        return toDateKey(value);
      case 'Line Number':
        return toNumberKey(value);
      case 'MAC Address':
        return toMacKey(value);
      case 'Switch Port':
        return toPortKeyLocal(value);
      default:
        return (value == null ? '' : String(value).toLowerCase());
    }
  }, []);

  const compareKeys = (a, b) => {
    if (Array.isArray(a) && Array.isArray(b)) {
      const len = Math.max(a.length, b.length);
      for (let i = 0; i < len; i++) {
        const av = a[i] ?? -Infinity;
        const bv = b[i] ?? -Infinity;
        if (av < bv) return -1;
        if (av > bv) return 1;
      }
      return 0;
    }
    if (typeof a === 'number' && typeof b === 'number') return a - b;
    return String(a).localeCompare(String(b));
  };

  const sortedData = React.useMemo(() => {
    if (!Array.isArray(data) || !orderBy) return data;
    const arr = data.map((row, idx) => ({ row, idx }));
    arr.sort((A, B) => {
      const aKey = getKey(orderBy, A.row[orderBy]);
      const bKey = getKey(orderBy, B.row[orderBy]);
      let cmp = compareKeys(aKey, bKey);
      if (order === 'desc') cmp = -cmp;
      if (cmp === 0) return A.idx - B.idx; // stable
      return cmp;
    });
    return arr.map(x => x.row);
  }, [data, orderBy, order, getKey]);

  // Compute date range for gradient coloring (newest -> orange, oldest -> red)
  const dateRange = React.useMemo(() => {
    try {
      if (!Array.isArray(data) || data.length === 0) return null;
      let minMs = Number.POSITIVE_INFINITY;
      let maxMs = Number.NEGATIVE_INFINITY;
      data.forEach((row) => {
        const v = row && row['Creation Date'];
        if (!v) return;
        const t = Date.parse(v);
        if (!Number.isFinite(t)) return;
        if (t < minMs) minMs = t;
        if (t > maxMs) maxMs = t;
      });
      if (!Number.isFinite(minMs) || !Number.isFinite(maxMs)) return null;
      if (minMs === Number.POSITIVE_INFINITY || maxMs === Number.NEGATIVE_INFINITY) return null;
      return { minMs, maxMs };
    } catch { return null; }
  }, [data]);

  // Map a date to a brighter orange (newest) -> deep red (oldest)
  // Also return a soft background pill color for better visibility
  const getDateVisual = React.useCallback((dateString) => {
    if (!dateString || !dateRange) return { color: 'text.primary', bg: 'transparent' };
    const tMs = Date.parse(dateString);
    if (!Number.isFinite(tMs)) return { color: 'text.primary', bg: 'transparent' };
    const { minMs, maxMs } = dateRange;
    const span = Math.max(1, maxMs - minMs);
    // Normalize so newest (maxMs) -> 0, oldest (minMs) -> 1
    const t = Math.min(1, Math.max(0, (maxMs - tMs) / span));
    // Hue: 35 (bright orange) -> 0 (red)
    const hue = 35 * (1 - t);
    const sat = 100; // %
    // Lightness: start brighter at newest (65%), fade to 40% at oldest
    const light = 40 + (65 - 40) * (1 - t);
    const color = `hsl(${hue} ${sat}% ${light}%)`;
    // Soft background pill using same hue, moderate lightness, low alpha
    const bgLight = 52; // middle lightness for background
    const alphaBg = 0.16; // subtle but visible
    const bg = `hsla(${hue}, ${sat}%, ${bgLight}%, ${alphaBg})`;
    return { color, bg };
  }, [dateRange]);

  // Helper: check if a date string is today (local time)
  const isToday = React.useCallback((dateString) => {
    if (!dateString) return false;
    const d = new Date(dateString);
    if (!Number.isFinite(d.getTime())) return false;
    const now = new Date();
    return d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate();
  }, []);

  // Removed unused getDateColor helper to satisfy lint

  const copyToClipboard = async (text) => {
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (error) {
      console.warn('Clipboard API failed, falling back to legacy method:', error);
    }

    // Fallback method using document.execCommand
    try {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      textArea.style.position = 'fixed';
      textArea.style.left = '-999999px';
      textArea.style.top = '-999999px';
      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();
      const result = document.execCommand('copy');
      document.body.removeChild(textArea);
      return result;
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
      return false;
    }
  };

  function convertToCiscoFormat(port) {
    if (!port || typeof port !== 'string') return port;
    const p = port.trim();
    // Already shortened
    if (p.startsWith('Gig ') || p.startsWith('Fas ')) return p;

    // GigabitEthernet full form
    if (p.startsWith('GigabitEthernet')) {
      const remainder = p.substring('GigabitEthernet'.length);
      return (`Gig ${remainder}`).replace(/\s+/g, ' ').trim();
    }
    // FastEthernet full form
    if (p.startsWith('FastEthernet')) {
      const remainder = p.substring('FastEthernet'.length);
      return (`Fas ${remainder}`).replace(/\s+/g, ' ').trim();
    }
    // Short forms like Gi1/0/32 or Fa1/0/32
    if (/^Gi\d/.test(p)) return p.replace(/^Gi/, 'Gig ');
    if (/^Fa\d/.test(p)) return p.replace(/^Fa/, 'Fas ');
    return p;
  }

  const formatMacDotted = (mac) => {
    if (!mac || typeof mac !== 'string') return mac;
    // Remove separators
    const cleaned = mac.replace(/[^A-Fa-f0-9]/g, '').toLowerCase();
    if (cleaned.length !== 12) return mac; // Not a standard MAC
    return `${cleaned.slice(0, 4)}.${cleaned.slice(4, 8)}.${cleaned.slice(8, 12)}`;
  };

  const handleCellClick = (header, content, rowData = null) => {

    if (header === "MAC Address" && onMacAddressClick) {
      // Start search immediately without waiting for clipboard
      onMacAddressClick(content);

      // Unified toast
      showCopyToast('Copied MAC address', content);

      // Copy to clipboard in background
      copyToClipboard(content).then(success => {
        if (!success) {
          toast.error(`❌ Copy failed`, {
            autoClose: 2000,
            pauseOnHover: true,
            pauseOnFocusLoss: false
          });
        }
      });
    } else if (header === "Switch Port" && onSwitchPortClick) {
      // Start search immediately without waiting for clipboard
      onSwitchPortClick(content);

      // Unified toast
      showCopyToast('Copied switch port', content);

      // Copy to clipboard in background
      copyToClipboard(content).then(success => {
        if (!success) {
          toast.error(`❌ Copy failed`, {
            autoClose: 2000,
            pauseOnHover: true,
            pauseOnFocusLoss: false
          });
        }
      });
    }
    // Note: Switch Hostname handling is now done directly in renderCellContent
  };

  const renderCellContent = (header, content, isArray = false, rowData = null) => {
    // IP Address mit Link
    if (header === "IP Address") {
      return (
        <Tooltip arrow placement="top" title={`Open http://${content}`}>
          <Typography
            variant="body2"
            component="a"
            href={`http://${content}`}
            target="_blank"
            rel="noopener noreferrer"
            sx={{
              textDecoration: 'underline',
              color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.6)' : 'text.secondary',
              cursor: 'pointer',
              '&:hover': {
                color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
                textDecoration: 'underline'
              }
            }}
          >
            {content}
          </Typography>
        </Tooltip>
      );
    }

    // Switch Hostname mit getrennten Klick-Bereichen
    if (header === "Switch Hostname") {
      // Split hostname in hostname Teil (vor erstem .) und Domain Teil
      const parts = content.split('.');
      const hostnameShort = parts[0] || content;
      const domainPart = parts.length > 1 ? '.' + parts.slice(1).join('.') : '';

      const copyHostnameTitle = `Copy hostname: ${hostnameShort}`;

      const sshTitle = sshUsername
        ? `Connect SSH ${sshUsername}@${content}`
        : `SSH connection (SSH username not set)`;

      return (
        <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center' }}>
          {/* Hostname short part - kopiert hostname Teil vor dem . */}
          <Tooltip arrow placement="top" title={copyHostnameTitle}>
            <Typography
              variant="body2"
              component="span"
              onClick={(e) => {
                e.stopPropagation();
                // Copy hostname short part (before first .)
                copyToClipboard(hostnameShort).then(success => {
                  if (success) {
                    showCopyToast('Copied hostname', hostnameShort);
                  } else {
                    toast.error(`❌ Copy failed`, {
                      autoClose: 2000,
                      pauseOnHover: true,
                      pauseOnFocusLoss: false
                    });
                  }
                });
              }}
              sx={{
                color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.8)' : '#4caf50',
                cursor: 'pointer',
                textDecoration: 'underline',
                '&:hover': {
                  color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 1)' : '#388e3c',
                  textDecoration: 'underline'
                }
              }}
            >
              {hostnameShort}
            </Typography>
          </Tooltip>

          {/* Domain part - SSH Verbindung */}
          {domainPart && (
            <Tooltip arrow placement="top" title={sshTitle}>
              <Typography
                variant="body2"
                component="span"
                onClick={(e) => {
                  e.stopPropagation();

                  // First: Copy Cisco port format
                  const ciscoFormat = rowData && rowData["Switch Port"] ? convertToCiscoFormat(rowData["Switch Port"]) : '';
                  if (ciscoFormat && ciscoFormat.trim() !== '') {
                    copyToClipboard(ciscoFormat).then(success => {
                      if (success) {
                        showCopyToast('Copied Cisco port', ciscoFormat);
                      } else {
                        toast.error(`❌ Copy failed`, {
                          autoClose: 2000,
                          pauseOnHover: true,
                          pauseOnFocusLoss: false
                        });
                      }
                    });
                  } else {
                    toast.warning('No switch port available to copy', {
                      autoClose: 2000,
                      pauseOnHover: true
                    });
                  }

                  // Second: SSH link functionality
                  if (sshUsername && sshUsername.trim() !== '') {
                    const sshUrl = `ssh://${sshUsername}@${content}`;
                    toast.success(`🔗 SSH: ${sshUsername}@${content}`, { autoClose: 1000, pauseOnHover: false });
                    setTimeout(() => { window.location.href = sshUrl; }, 150);
                  } else {
                    // If no SSH username, show warning but don't copy hostname again
                    const ToastContent = () => (
                      <div>
                        📋 Copied Cisco port! ⚠️ SSH username not configured!{' '}
                        <span
                          onClick={() => {
                            navigateToSettings();
                            toast.dismiss();
                          }}
                          style={{
                            color: '#4f46e5',
                            textDecoration: 'underline',
                            cursor: 'pointer',
                            fontWeight: 'bold'
                          }}
                        >
                          Go to Settings
                        </span> to set your SSH username.
                      </div>
                    );
                    toast.warning(<ToastContent />, {
                      autoClose: 6000,
                      pauseOnHover: true,
                      pauseOnFocusLoss: false
                    });
                  }
                }}
                sx={{
                  color: theme => theme.palette.mode === 'dark' ? 'rgba(139, 195, 74, 0.8)' : '#689f38',
                  cursor: 'pointer',
                  textDecoration: 'underline',
                  '&:hover': {
                    color: theme => theme.palette.mode === 'dark' ? 'rgba(139, 195, 74, 1)' : '#558b2f',
                    textDecoration: 'underline'
                  }
                }}
              >
                {domainPart}
              </Typography>
            </Tooltip>
          )}

          {/* SSH Icon - click opens SSH, no switch port copy */}
          <Tooltip arrow placement="top" title={sshTitle}>
            <Terminal
              className="ssh-icon"
              onClick={(e) => {
                e.stopPropagation();
                if (sshUsername && sshUsername.trim() !== '') {
                  const sshUrl = `ssh://${sshUsername}@${content}`;
                  toast.success(`🔗 SSH: ${sshUsername}@${content}`, { autoClose: 1000, pauseOnHover: false });
                  setTimeout(() => { window.location.href = sshUrl; }, 150);
                } else {
                  const ToastContent = () => (
                    <div>
                      ⚠️ SSH username not configured!{' '}
                      <span
                        onClick={() => {
                          navigateToSettings();
                          toast.dismiss();
                        }}
                        style={{
                          color: '#4f46e5',
                          textDecoration: 'underline',
                          cursor: 'pointer',
                          fontWeight: 'bold'
                        }}
                      >
                        Go to Settings
                      </span> to set your SSH username.
                    </div>
                  );
                  toast.warning(<ToastContent />, { autoClose: 6000, pauseOnHover: true, pauseOnFocusLoss: false });
                }
              }}
              sx={{
                color: theme => sshUsername
                  ? (theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.6)' : '#4caf50')
                  : (theme.palette.mode === 'dark' ? 'rgba(156, 163, 175, 0.6)' : '#9e9e9e'),
                fontSize: '14px',
                ml: 0.5,
                verticalAlign: 'middle',
                cursor: 'pointer'
              }}
            />
          </Tooltip>
        </Box>
      );
    }

    // File Name mit Download
    if (header === "File Name") {
      const handleDownload = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        const filename = content;
        try {
          const resp = await fetch(`/api/files/download/${encodeURIComponent(filename)}`, {
            method: 'GET',
            headers: { 'Accept': 'text/csv' }
          });
          if (!resp.ok) {
            const text = await resp.text().catch(() => '');
            toast.error(`❌ Download failed (${resp.status})`);
            console.error('Download error response:', resp.status, text);
            return;
          }
          const blob = await resp.blob();
          if (blob.size === 0) {
            toast.error('❌ Empty file');
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
          showCopyToast('Downloaded file', filename);
        } catch (err) {
          console.error('Download exception', err);
          toast.error('❌ Download error');
        }
      };
      return (
        <Tooltip arrow placement="top" title={`Download ${content}`}>
          <Typography
            variant="body2"
            component="a"
            href={`/api/files/download/${content}`}
            onClick={handleDownload}
            sx={{
              textDecoration: 'underline',
              color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.6)' : 'text.secondary',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              '&:hover': {
                color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
                textDecoration: 'underline',
                '& .download-icon': {
                  color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.6)' : 'text.secondary'
                }
              }
            }}
          >
            {content}
            <Download
              className="download-icon"
              sx={{
                color: 'text.disabled',
                fontSize: '12px',
                verticalAlign: 'middle'
              }}
            />
          </Typography>
        </Tooltip>
      );
    }

    // Creation Date mit Farb-Gradient (neueste = helles Orange -> älteste = tiefes Rot)
    if (header === "Creation Date" && content) {
      if (isToday(content)) {
        return (
          <Typography sx={{
            color: (theme) => theme.palette.success.main,
            fontWeight: 800,
            fontSize: '0.9rem',
            backgroundColor: 'rgba(76, 175, 80, 0.18)', // soft green pill
            px: 0.75,
            py: 0.25,
            borderRadius: 1
          }}>
            {content}
          </Typography>
        );
      }
      const { color, bg } = getDateVisual(content);
      return (
        <Typography sx={{
          color,
          fontWeight: 700,
          fontSize: '0.9rem',
          backgroundColor: bg,
          px: 0.75,
          py: 0.25,
          borderRadius: 1
        }}>
          {content}
        </Typography>
      );
    }

    // Switch Port with tooltip for full value
    if (header === "Switch Port") {
      return (
        <Tooltip arrow placement="top" title={content || ''}>
          <Typography variant="body2" sx={{
            color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
            fontWeight: 400,
          }}>
            {content}
          </Typography>
        </Tooltip>
      );
    }

    // Line Number with KEM replacement logic (KEM / KEM 2 merged earlier into Line Number)
    if (header === 'Line Number' && content) {
      // Detect KEM tokens appended (they were appended with spaces, e.g. "1001 KEM" or "1001 KEM KEM2")
      const parts = String(content).split(/\s+/).filter(Boolean);
      const kemCount = parts.filter(p => p.toUpperCase().startsWith('KEM')).length;
      // Base line number is first numeric/token not starting with KEM
      const base = parts.filter(p => !p.toUpperCase().startsWith('KEM')).join(' ');
      return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
          <Typography variant="body2" sx={{
            color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
            fontWeight: 400
          }}>{base}</Typography>
          {kemCount > 0 && (
            <Tooltip arrow placement="top" title={`${kemCount} KEM module${kemCount > 1 ? 's' : ''}`}>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                {Array.from({ length: kemCount }).map((_, i) => (
                  <img
                    key={i}
                    src={kemIcon}
                    alt={`KEM module ${i + 1}`}
                    style={{
                      width: 18,
                      height: 11,
                      objectFit: 'contain',
                      display: 'block',
                      opacity: 0.95,
                      filter: 'drop-shadow(0 0 1px rgba(0,0,0,0.45))',
                      marginLeft: i === 0 ? 0 : -6, // even tighter overlap
                      paddingLeft: 0,
                      zIndex: kemCount - i // keep leftmost on top for clearer edges
                    }}
                  />
                ))}
              </Box>
            </Tooltip>
          )}
        </Box>
      );
    }

    // Standard Text
    return (
      <Typography variant="body2" sx={{
        color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
        fontWeight: 400
      }}>
        {content}
      </Typography>
    );
  };

  if (!data || !headers) {
    return (
      <Box sx={{ py: 4, textAlign: 'center' }}>
        <Typography variant="h6" color="text.secondary">
          No data available
        </Typography>
      </Box>
    );
  }

  return (
    <TableContainer
      component={Paper}
      elevation={1}
      sx={{
        borderRadius: 1,
        overflowX: 'auto'
      }}
    >
      <Table>
        <TableHead>
          <TableRow>
            {showRowNumbers && (
              <TableCell sx={{
                fontWeight: 600,
                fontSize: '0.85rem',
                color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'text.secondary',
                borderBottom: theme => `2px solid ${theme.palette.divider}`,
                backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(55, 65, 81, 0.5)' : theme.palette.background.paper
              }}>
                #
              </TableCell>
            )}
            {filteredHeaders.map((header) => (
              <TableCell
                key={header}
                align="left"
                sx={{
                  fontWeight: 600,
                  fontSize: '0.85rem',
                  color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'text.secondary',
                  borderBottom: theme => `2px solid ${theme.palette.divider}`,
                  backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(55, 65, 81, 0.5)' : theme.palette.background.paper,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  px: header === 'Voice VLAN' ? 1 : 1.5,
                  minWidth: headerWidthMap[header] || 140,
                }}
              >
                <TableSortLabel
                  active={orderBy === header}
                  direction={orderBy === header ? order : 'asc'}
                  onClick={() => handleSort(header)}
                >
                  {(() => {
                    const display = (labelMap && labelMap[header]) || header;
                    if (header === 'Voice VLAN' && display === 'Voice VLAN') {
                      return (
                        <Box component="span" sx={{ display: 'block', lineHeight: 1.05, whiteSpace: 'normal' }}>
                          Voice<br />VLAN
                        </Box>
                      );
                    }
                    return display;
                  })()}
                </TableSortLabel>
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {Array.isArray(data) ? (
            data.length === 0 ? (
              <TableRow>
                <TableCell colSpan={filteredHeaders.length + (showRowNumbers ? 1 : 0)} align="center">
                  <Box sx={{ py: 4 }}>
                    <Typography variant="h6" color="text.secondary">
                      No data found
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Try adjusting your search terms or filters
                    </Typography>
                  </Box>
                </TableCell>
              </TableRow>
            ) : (
              (sortedData || data).map((row, index) => (
                <TableRow
                  key={index}
                  sx={{
                    backgroundColor: theme => theme.palette.mode === 'dark'
                      ? 'rgba(31, 41, 55, 0.5)'
                      : 'transparent',
                    borderBottom: theme => `1px solid ${theme.palette.divider}`,
                    '&:hover': {
                      backgroundColor: theme => theme.palette.mode === 'dark'
                        ? 'rgba(59, 130, 246, 0.1)'
                        : 'rgba(0, 0, 0, 0.04)',
                    },
                    '&:nth-of-type(even)': {
                      backgroundColor: theme => theme.palette.mode === 'dark'
                        ? 'rgba(55, 65, 81, 0.3)'
                        : 'transparent',
                    }
                  }}
                >
                  {showRowNumbers && (
                    <TableCell sx={{
                      fontWeight: 500,
                      color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
                      fontSize: '0.9rem'
                    }}>
                      {index + 1}
                    </TableCell>
                  )}
                  {filteredHeaders.map((header) => {
                    const cellContent = row[header];
                    return (
                      <TableCell
                        key={`${index}-${header}`}
                        onClick={() => handleCellClick(header, cellContent, row)}
                        align={header === 'Voice VLAN' ? 'center' : ((header === 'MAC Address' || header === 'Switch Port') ? 'right' : 'left')}
                        sx={{
                          cursor: (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? "pointer" : "default",
                          whiteSpace: 'nowrap',
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          px: header === 'Voice VLAN' ? 1 : 1.5,
                          minWidth: headerWidthMap[header] || 140,
                          '&:hover': (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? {
                            backgroundColor: theme => alpha(theme.palette.secondary.main, 0.1)
                          } : {}
                        }}
                      >
                        {header === "Switch Port" ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                            {renderCellContent(header, cellContent, true, row)}
                            <Tooltip title={convertToCiscoFormat(cellContent) || ''} placement="top" arrow>
                              <Chip
                                label="Cisco"
                                size="small"
                                sx={{
                                  height: '20px',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  bgcolor: '#00bceb',
                                  color: '#fff',
                                  '&:hover': { bgcolor: '#00acd0' },
                                  letterSpacing: '0.5px'
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const ciscoFormat = convertToCiscoFormat(cellContent);
                                  showCopyToast('Copied Cisco port', ciscoFormat);
                                  copyToClipboard(ciscoFormat).catch(() => {
                                    toast.error('❌ Copy failed', { autoClose: 2000 });
                                  });
                                }}
                              />
                            </Tooltip>
                          </Box>
                        ) : header === "MAC Address" ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                            {renderCellContent(header, cellContent, true, row)}
                            <Tooltip title={formatMacDotted(cellContent) || ''} placement="top" arrow>
                              <Chip
                                label="Cisco"
                                size="small"
                                sx={{
                                  height: '20px',
                                  fontSize: '0.7rem',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  bgcolor: '#00bceb',
                                  color: '#fff',
                                  '&:hover': { bgcolor: '#00acd0' },
                                  letterSpacing: '0.5px'
                                }}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  const formatted = formatMacDotted(cellContent);
                                  showCopyToast('Copied MAC (dotted)', formatted);
                                  copyToClipboard(formatted).catch(() => {
                                    toast.error('❌ Copy failed', { autoClose: 2000 });
                                  });
                                }}
                              />
                            </Tooltip>
                          </Box>
                        ) : (
                          renderCellContent(header, cellContent, true, row)
                        )}
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))
            )
          ) : (
            // Single object case (nicht-Array data)
            <TableRow
              sx={{
                backgroundColor: theme => theme.palette.mode === 'dark'
                  ? 'rgba(31, 41, 55, 0.5)'
                  : 'transparent',
                borderBottom: theme => `1px solid ${theme.palette.divider}`,
                '&:hover': {
                  backgroundColor: theme => theme.palette.mode === 'dark'
                    ? 'rgba(59, 130, 246, 0.1)'
                    : 'rgba(0, 0, 0, 0.04)',
                },
                transition: 'all 0.2s ease'
              }}
            >
              {showRowNumbers && (
                <TableCell sx={{
                  fontWeight: 500,
                  color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary',
                  fontSize: '0.9rem'
                }}>
                  1
                </TableCell>
              )}
              {filteredHeaders.map((header) => {
                const cellContent = data[header];
                return (
                  <TableCell
                    key={header}
                    onClick={() => handleCellClick(header, cellContent, data)}
                    align={header === 'Voice VLAN' ? 'center' : ((header === 'MAC Address' || header === 'Switch Port') ? 'right' : 'left')}
                    sx={{
                      cursor: (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? "pointer" : "default",
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      px: header === 'Voice VLAN' ? 1 : 1.5,
                      minWidth: headerWidthMap[header] || 140,
                      '&:hover': (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? {
                        backgroundColor: theme => alpha(theme.palette.secondary.main, 0.1)
                      } : {}
                    }}
                  >
                    {header === "Switch Port" ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                        {renderCellContent(header, cellContent, false)}
                        <Tooltip title={convertToCiscoFormat(cellContent) || ''} placement="top" arrow>
                          <Chip
                            label="Cisco"
                            size="small"
                            sx={{
                              height: '20px',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              bgcolor: '#00bceb',
                              color: '#fff',
                              '&:hover': { bgcolor: '#00acd0' },
                              letterSpacing: '0.5px'
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              const ciscoFormat = convertToCiscoFormat(cellContent);
                              showCopyToast('Copied Cisco port', ciscoFormat);
                              copyToClipboard(ciscoFormat).catch(() => {
                                toast.error('❌ Copy failed', { autoClose: 2000 });
                              });
                            }}
                          />
                        </Tooltip>
                      </Box>
                    ) : header === "MAC Address" ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, justifyContent: 'flex-end' }}>
                        {renderCellContent(header, cellContent, false)}
                        <Tooltip title={formatMacDotted(cellContent) || ''} placement="top" arrow>
                          <Chip
                            label="Cisco"
                            size="small"
                            sx={{
                              height: '20px',
                              fontSize: '0.7rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                              bgcolor: '#00bceb',
                              color: '#fff',
                              '&:hover': { bgcolor: '#00acd0' },
                              letterSpacing: '0.5px'
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              const formatted = formatMacDotted(cellContent);
                              showCopyToast('Copied MAC (dotted)', formatted);
                              copyToClipboard(formatted).catch(() => {
                                toast.error('❌ Copy failed', { autoClose: 2000 });
                              });
                            }}
                          />
                        </Tooltip>
                      </Box>
                    ) : (
                      renderCellContent(header, cellContent, false, data)
                    )}
                  </TableCell>
                );
              })}
            </TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// Memoize to prevent unnecessary rerenders on theme toggles or parent updates when props are equal
const MemoDataTable = React.memo(DataTable);
export default MemoDataTable;