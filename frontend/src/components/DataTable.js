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
import { Download } from '@mui/icons-material';
import { toast } from 'react-toastify';

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

  const handleCellClick = (header, content) => {
    if (header === "MAC Address" && onMacAddressClick) {
      navigator.clipboard.writeText(content);
      toast.success("Copied to clipboard");
      onMacAddressClick(content);
    } else if (header === "Switch Port" && onSwitchPortClick) {
      navigator.clipboard.writeText(content);
      toast.success("Copied to clipboard");
      onSwitchPortClick(content);
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
            alignItems: 'flex-end',
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
              fontSize: '12px'
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
            {headers.map((header) => (
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
                <TableCell colSpan={headers.length + (showRowNumbers ? 1 : 0)} align="center">
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
                  {headers.map((header) => {
                    const cellContent = row[header];
                    return (
                      <TableCell 
                        key={`${index}-${header}`}
                        onClick={() => handleCellClick(header, cellContent)}
                        sx={{ 
                          cursor: (header === "MAC Address" || header === "Switch Port") ? "pointer" : "default",
                          whiteSpace: header === "Switch Port" ? "nowrap" : "normal",
                          '&:hover': (header === "MAC Address" || header === "Switch Port") ? {
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
                                fontWeight: 600
                              }}
                              color="primary"
                              variant="outlined"
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
              {headers.map((header) => {
                const cellContent = data[header];
                return (
                  <TableCell 
                    key={header}
                    onClick={() => handleCellClick(header, cellContent)}
                    sx={{ 
                      cursor: (header === "MAC Address" || header === "Switch Port") ? "pointer" : "default",
                      whiteSpace: header === "Switch Port" ? "nowrap" : "normal",
                      '&:hover': (header === "MAC Address" || header === "Switch Port") ? {
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
                            fontWeight: 600
                          }}
                          color="primary"
                          variant="outlined"
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