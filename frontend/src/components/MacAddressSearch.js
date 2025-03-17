import React, { useState } from 'react';
import { 
  Box, 
  TextField, 
  Button, 
  Typography, 
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import useSearchMacAddress from '../hooks/useSearchMacAddress';

/**
 * Component for searching MAC addresses and displaying results
 */
function MacAddressSearch() {
  const [macAddress, setMacAddress] = useState('');
  const [includeHistorical, setIncludeHistorical] = useState(true);
  const { search, results, loading, error } = useSearchMacAddress();

  const handleSearch = async () => {
    if (!macAddress) return;
    await search(macAddress, includeHistorical);
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" gutterBottom>
        MAC Address Search
      </Typography>
      
      <Paper elevation={2} sx={{ p: 3, mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'flex-start', mb: 2 }}>
          <TextField
            label="MAC Address"
            placeholder="e.g., 00:1A:2B:3C:4D:5E"
            variant="outlined"
            fullWidth
            value={macAddress}
            onChange={(e) => setMacAddress(e.target.value)}
            onKeyPress={handleKeyPress}
            helperText="Enter a MAC address to search for in the netspeed CSV files"
            sx={{ mr: 2 }}
          />
          <Button 
            variant="contained" 
            color="primary" 
            onClick={handleSearch}
            startIcon={<SearchIcon />}
            sx={{ height: 56 }}
            disabled={loading || !macAddress}
          >
            Search
          </Button>
        </Box>
        
        <FormControlLabel
          control={
            <Checkbox
              checked={includeHistorical}
              onChange={(e) => setIncludeHistorical(e.target.checked)}
              color="primary"
            />
          }
          label="Include historical files in search"
        />
      </Paper>

      {/* Error message */}
      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Loading indicator */}
      {loading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', mb: 3 }}>
          <CircularProgress />
        </Box>
      )}

      {/* Results table */}
      {results && !loading && (
        <Box>
          <Typography variant="h6" gutterBottom>
            Search Results
          </Typography>
          
          <Alert 
            severity={results.success ? "success" : "info"} 
            sx={{ mb: 2 }}
          >
            {results.message}
          </Alert>
          
          {results.data && results.headers && (
            <TableContainer component={Paper}>
              <Table sx={{ minWidth: 650 }} aria-label="search results table">
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    {results.headers.map((header) => (
                      <TableCell key={header}>
                        <Typography variant="subtitle2">
                          <strong>{header}</strong>
                        </Typography>
                      </TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  <TableRow>
                    {results.headers.map((header) => (
                      <TableCell key={header}>
                        {results.data[header]}
                      </TableCell>
                    ))}
                  </TableRow>
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Box>
      )}
    </Box>
  );
}

export default MacAddressSearch;
