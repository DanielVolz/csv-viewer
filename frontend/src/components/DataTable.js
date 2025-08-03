import React from 'react';
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
  alpha
} from '@mui/material';
import { Download, Terminal } from '@mui/icons-material';
import { toast } from 'react-toastify';
import { useSettings } from '../contexts/SettingsContext';

/**
 * Gemeinsame DataTable-Komponente für Preview und Suchergebnisse
 * Eliminiert Code-Duplikation und sorgt für konsistente Darstellung
 */
function DataTable({ 
  headers, 
  data, 
  showRowNumbers = false,
  onMacAddressClick,
  onSwitchPortClick 
}) {
  const { getEnabledColumnHeaders, sshUsername, navigateToSettings } = useSettings();
  
  // Get custom column configuration from settings
  const enabledHeaders = getEnabledColumnHeaders();
  
  // Filter headers based on settings, but keep the original order from the settings
  const filteredHeaders = enabledHeaders.filter(header => headers.includes(header));
  
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

  const convertToCiscoFormat = (port) => {
    if (!port || typeof port !== 'string') {
      console.log('Invalid port data:', port);
      return port;
    }
    
    console.log('Converting port:', port); // Debug log
    
    // Convert formats like "GigabitEthernet1/0/2/74" to "Gig 0/2/74"
    const ciscoFormatRegex = /^GigabitEthernet(\d+)\/(\d+)\/(\d+)\/(\d+)$/i;
    const match = port.match(ciscoFormatRegex);
    
    if (match) {
      const [, , slot, module, portNum] = match;
      const result = `Gig ${slot}/${module}/${portNum}`;
      console.log('Converted to Cisco format:', result);
      return result;
    }
    
    // Try other common formats
    // Format: "Gi1/0/2/74" or "Gi 1/0/2/74"
    const shortGigRegex = /^Gi\s?(\d+)\/(\d+)\/(\d+)\/(\d+)$/i;
    const shortMatch = port.match(shortGigRegex);
    if (shortMatch) {
      const [, , slot, module, portNum] = shortMatch;
      const result = `Gig ${slot}/${module}/${portNum}`;
      console.log('Converted short format to Cisco:', result);
      return result;
    }
    
    // If it's already in a short format, keep it
    if (port.match(/^Gig\s+\d+\/\d+\/\d+$/i)) {
      console.log('Already in correct Cisco format:', port);
      return port;
    }
    
    console.log('No conversion pattern matched, returning original:', port);
    // If it doesn't match any expected format, return the original
    return port;
  };

  const handleCellClick = async (header, content, rowData = null) => {
    console.log('Cell clicked:', header, content, 'SSH Username:', sshUsername); // Debug log
    
    if (header === "MAC Address" && onMacAddressClick) {
      const success = await copyToClipboard(content);
      if (success) {
        toast.success(`📋 MAC Address copied: ${content}`, {
          autoClose: 3000,
          pauseOnHover: true,
          pauseOnFocusLoss: false
        });
      } else {
        toast.error(`❌ Failed to copy MAC Address`, {
          autoClose: 5000,
          pauseOnHover: true,
          pauseOnFocusLoss: false
        });
      }
      onMacAddressClick(content);
    } else if (header === "Switch Port" && onSwitchPortClick) {
      const success = await copyToClipboard(content);
      if (success) {
        toast.success(`📋 Switch Port copied: ${content}`, {
          autoClose: 3000,
          pauseOnHover: true,
          pauseOnFocusLoss: false
        });
      } else {
        toast.error(`❌ Failed to copy Switch Port`, {
          autoClose: 5000,
          pauseOnHover: true,
          pauseOnFocusLoss: false
        });
      }
      onSwitchPortClick(content);
    } else if (header === "Switch Hostname" && content) {
      console.log('Switch Hostname clicked, SSH Username:', sshUsername); // Debug log
      // SSH link functionality
      if (sshUsername && sshUsername.trim() !== '') {
        // First copy port in Cisco format if available (while we still have user activation)
        let portCopySuccess = false;
        let ciscoFormat = '';
        
        if (rowData && rowData["Switch Port"]) {
          console.log('Switch Port data:', rowData["Switch Port"]); // Debug log
          ciscoFormat = convertToCiscoFormat(rowData["Switch Port"]);
          console.log('Cisco format:', ciscoFormat); // Debug log
          
          if (ciscoFormat && ciscoFormat.trim() !== '') {
            portCopySuccess = await copyToClipboard(ciscoFormat);
          }
        }
        
        // Then open SSH link
        const sshUrl = `ssh://${sshUsername}@${content}`;
        console.log('Opening SSH URL:', sshUrl); // Debug log
        window.open(sshUrl, '_blank');
        
        // Show SSH link success
        toast.success(`🔗 SSH link opened: ${sshUsername}@${content}`, {
          autoClose: 3000,
          pauseOnHover: true,
          pauseOnFocusLoss: false
        });
        
        // Show port copy result if port was available
        if (rowData && rowData["Switch Port"] && ciscoFormat && ciscoFormat.trim() !== '') {
          if (portCopySuccess) {
            toast.success(`📋 Cisco port copied: ${ciscoFormat}`, {
              autoClose: 3000,
              pauseOnHover: true,
              pauseOnFocusLoss: false
            });
          } else {
            toast.error(`❌ Failed to copy Cisco port: ${ciscoFormat}`, {
              autoClose: 5000,
              pauseOnHover: true,
              pauseOnFocusLoss: false
            });
          }
        }
      } else {
        console.log('No SSH username, copying hostname to clipboard'); // Debug log
        const success = await copyToClipboard(content);
        
        // Custom toast content with clickable link
        const ToastContent = () => (
          <div>
            {success ? '📋 Hostname copied! ' : '❌ Failed to copy! '}
            ⚠️ SSH username not configured!{' '}
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
      }
    }
  };

  const renderCellContent = (header, content, isArray = false) => {
    // IP Address mit Link
    if (header === "IP Address") {
      return (
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
      );
    }
    
    // Switch Hostname mit SSH Link
    if (header === "Switch Hostname") {
      return (
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
      );
    }
    
    // File Name mit Download
    if (header === "File Name") {
      return (
        <Typography 
          variant="body2"
          component="a"
          href={`/api/files/download/${content}`}
          download
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
              <TableCell key={header} sx={{ 
                fontWeight: 600, 
                fontSize: '0.85rem',
                color: theme => theme.palette.mode === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'text.secondary',
                borderBottom: theme => `2px solid ${theme.palette.divider}`,
                backgroundColor: theme => theme.palette.mode === 'dark' ? 'rgba(55, 65, 81, 0.5)' : 'rgba(0, 0, 0, 0.02)'
              }}>
                {header}
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
              data.map((row, index) => (
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
                        sx={{ 
                          cursor: (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? "pointer" : "default",
                          whiteSpace: header === "Switch Port" ? "nowrap" : "normal",
                          '&:hover': (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? {
                            backgroundColor: theme => alpha(theme.palette.secondary.main, 0.1)
                          } : {}
                        }}
                      >
                        {header === "Switch Port" ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            {renderCellContent(header, cellContent, true)}
                            <Chip 
                              label="cisco"
                              size="small"
                              sx={{ 
                                height: '20px',
                                fontSize: '0.7rem',
                                fontWeight: 600,
                                cursor: 'pointer'
                              }}
                              color="primary"
                              variant="outlined"
                              onClick={async (e) => {
                                e.stopPropagation();
                                const ciscoFormat = convertToCiscoFormat(cellContent);
                                const success = await copyToClipboard(ciscoFormat);
                                if (success) {
                                  toast.success(`📋 Cisco format copied: ${ciscoFormat}`, {
                                    autoClose: 3000,
                                    pauseOnHover: true,
                                    pauseOnFocusLoss: false
                                  });
                                } else {
                                  toast.error(`❌ Failed to copy Cisco format`, {
                                    autoClose: 5000,
                                    pauseOnHover: true,
                                    pauseOnFocusLoss: false
                                  });
                                }
                              }}
                            />
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
                    sx={{ 
                      cursor: (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? "pointer" : "default",
                      whiteSpace: header === "Switch Port" ? "nowrap" : "normal",
                      '&:hover': (header === "MAC Address" || header === "Switch Port" || header === "Switch Hostname") ? {
                        backgroundColor: theme => alpha(theme.palette.secondary.main, 0.1)
                      } : {}
                    }}
                  >
                    {header === "Switch Port" ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {renderCellContent(header, cellContent, false)}
                        <Chip 
                          label="cisco"
                          size="small"
                          sx={{ 
                            height: '20px',
                            fontSize: '0.7rem',
                            fontWeight: 600,
                            cursor: 'pointer'
                          }}
                          color="primary"
                          variant="outlined"
                          onClick={async (e) => {
                            e.stopPropagation();
                            const ciscoFormat = convertToCiscoFormat(cellContent);
                            const success = await copyToClipboard(ciscoFormat);
                            if (success) {
                              toast.success(`📋 Cisco format copied: ${ciscoFormat}`, {
                                autoClose: 3000,
                                pauseOnHover: true,
                                pauseOnFocusLoss: false
                              });
                            } else {
                              toast.error(`❌ Failed to copy Cisco format`, {
                                autoClose: 5000,
                                pauseOnHover: true,
                                pauseOnFocusLoss: false
                              });
                            }
                          }}
                        />
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

export default DataTable;