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
  labelMap
}) {
  const { columns, getEnabledColumnHeaders, sshUsername, navigateToSettings } = useSettings();

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
    'Serial Number': 160,
    'Model Name': 180,
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
  const enabledHeaders = React.useMemo(() => {
    if (Array.isArray(columns) && columns.length > 0) {
      return columns.filter(c => c.enabled).map(c => c.id);
    }
    // Fallback: if columns not loaded yet, allow all provided headers
    return Array.isArray(headers) ? headers : [];
  }, [columns, headers]);

  // Filter headers based on settings, but keep the original order from the settings
  // Also remove any CSV header literally named '#' to avoid a duplicate '#' column
  const filteredHeaders = enabledHeaders
    .filter(header => header !== '#')
    .filter(header => header !== 'MAC Address 2')
    .filter(header => headers.includes(header));

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

  const toPortKey = (v) => {
    if (!v || typeof v !== 'string') return [0];
    const s = convertToCiscoFormat(v) || String(v);
    const typeWeight = /^Gig\b/.test(s) ? 2 : /^Fas\b/.test(s) ? 1 : 0;
    const nums = s.match(/\d+/g) || [];
    const parts = nums.map(n => parseInt(n, 10));
    return [typeWeight, ...parts];
  };

  const getKey = (header, value) => {
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
        return toPortKey(value);
      default:
        return (value == null ? '' : String(value).toLowerCase());
    }
  };

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
  }, [data, orderBy, order]);

  const getDateColor = (dateString) => {
    if (!dateString) return 'inherit';

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const fileDate = new Date(dateString);
    fileDate.setHours(0, 0, 0, 0);

    const diffTime = fileDate - today;
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return 'success.main';
    else if (diffDays > 0 && diffDays <= 14) return 'warning.main';
    else if (diffDays < 0 && diffDays >= -14) return 'warning.main';
    else return 'error.main';
  };

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
    } else if (header === "Switch Hostname" && content) {
      // SSH link functionality
      if (sshUsername && sshUsername.trim() !== '') {
        const sshUrl = `ssh://${sshUsername}@${content}`;
        const doNavigate = () => { window.location.href = sshUrl; };

        // Try to copy Cisco port BEFORE navigation (preserve user gesture)
        const tryCopyThenNavigate = async () => {
          let copied = false;
          const ciscoFormat = rowData && rowData["Switch Port"] ? convertToCiscoFormat(rowData["Switch Port"]) : '';
          if (ciscoFormat && ciscoFormat.trim() !== '') {
            try {
              copied = await copyToClipboard(ciscoFormat);
            } catch (_) {
              copied = false;
            }
            if (copied) {
              showCopyToast('Copied Cisco port', ciscoFormat, { autoClose: 1200, pauseOnHover: true });
            } else {
              toast.error(`❌ Failed to copy Cisco port: ${ciscoFormat}`, {
                autoClose: 2000,
                pauseOnHover: true,
                pauseOnFocusLoss: false
              });
            }
          }
          // Show SSH success just before navigating
          toast.success(`🔗 SSH: ${sshUsername}@${content}`, { autoClose: 1000, pauseOnHover: false });
          // Small delay to let the toast render, then navigate to ssh:// handler
          setTimeout(doNavigate, 150);
        };

        tryCopyThenNavigate();
      } else {
        // Show warning immediately, copy in background
        const ToastContent = () => (
          <div>
            📋 Copied hostname! ⚠️ SSH username not configured!{' '}
            <span
              onClick={() => {
                navigateToSettings();
                toast.dismiss(); // Close this toast
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

        toast.error(<ToastContent />, {
          autoClose: false,
          closeOnClick: false,
          hideProgressBar: true,
          closeButton: true,
          pauseOnHover: true
        });

        // Copy hostname in background
        copyToClipboard(content).catch(() => {
          // Silent fail - hostname copy is secondary
        });
      }
    }
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

    // Switch Hostname mit SSH Link
    if (header === "Switch Hostname") {
      const title = sshUsername
        ? `Open SSH ${sshUsername}@${content}`
        : 'Copy hostname (SSH username not set)';
      return (
        <Tooltip arrow placement="top" title={title}>
          <Typography
            variant="body2"
            component="span"
            sx={{
              textDecoration: sshUsername ? 'underline' : 'none',
              color: theme => {
                if (sshUsername) {
                  return theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.8)' : '#2e7d32';
                }
                return theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.87)' : 'text.primary';
              },
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              '&:hover': {
                color: theme => {
                  if (sshUsername) {
                    return theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 1)' : '#1b5e20';
                  } else {
                    return theme.palette.mode === 'dark' ? 'rgba(255, 193, 7, 0.8)' : '#f57c00';
                  }
                },
                textDecoration: 'underline',
                '& .ssh-icon': {
                  color: theme => sshUsername
                    ? (theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 1)' : '#1b5e20')
                    : (theme.palette.mode === 'dark' ? 'rgba(255, 193, 7, 0.8)' : '#f57c00')
                }
              }
            }}
          >
            {content}
            <Terminal
              className="ssh-icon"
              sx={{
                color: theme => sshUsername
                  ? (theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.6)' : '#4caf50')
                  : (theme.palette.mode === 'dark' ? 'rgba(156, 163, 175, 0.6)' : '#9e9e9e'),
                fontSize: '14px',
                ml: 0.5,
                verticalAlign: 'middle'
              }}
            />
          </Typography>
        </Tooltip>
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

    // Creation Date mit Farb-Kodierung
    if (header === "Creation Date" && content) {
      return (
        <Typography sx={{
          color: getDateColor(content),
          fontWeight: 500,
          fontSize: '0.9rem'
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
                backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(55, 65, 81, 0.5)' : 'rgba(0, 0, 0, 0.02)'
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
                  backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(55, 65, 81, 0.5)' : 'rgba(0, 0, 0, 0.02)',
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
                    const display = labelMap && labelMap[header] ? labelMap[header] : header;
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
                      : 'rgba(0, 0, 0, 0.01)',
                    borderBottom: theme => `1px solid ${theme.palette.divider}`,
                    '&:hover': {
                      backgroundColor: theme => theme.palette.mode === 'dark'
                        ? 'rgba(59, 130, 246, 0.1)'
                        : 'rgba(0, 0, 0, 0.04)',
                    },
                    '&:nth-of-type(even)': {
                      backgroundColor: theme => theme.palette.mode === 'dark'
                        ? 'rgba(55, 65, 81, 0.3)'
                        : 'rgba(0, 0, 0, 0.02)',
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
                            {renderCellContent(header, cellContent, true)}
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
                            {renderCellContent(header, cellContent, true)}
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
                          renderCellContent(header, cellContent, true)
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
                  : 'rgba(0, 0, 0, 0.01)',
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
                      renderCellContent(header, cellContent, false)
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

export default React.memo(DataTable);