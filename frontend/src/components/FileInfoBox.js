import React, { useState, useEffect } from 'react';
import { 
  Paper, 
  Typography, 
  Box, 
  CircularProgress, 
  Grid, 
  Chip,
  Divider,
  CardContent 
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile';
import EventIcon from '@mui/icons-material/Event';
import PhoneAndroidIcon from '@mui/icons-material/PhoneAndroid';
import axios from 'axios';

const FileInfoBox = () => {
  const [fileInfo, setFileInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchFileInfo = async () => {
      try {
        setLoading(true);
        const response = await axios.get('/api/files/netspeed_info');
        const data = response.data;
        
        if (data.success) {
          setFileInfo(data);
        } else {
          setError(data.message || 'Failed to fetch file information');
        }
      } catch (err) {
        setError('Error fetching file information. Please try again later.');
        console.error('Error fetching file info:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchFileInfo();
  }, []);

  if (loading) {
    return (
      <Paper elevation={1} sx={{ p: 2, mb: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress size={24} />
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper 
        elevation={1} 
        sx={{ 
          p: 2, 
          mb: 3, 
          backgroundColor: '#fff4e5', 
          color: '#663c00'
        }}
      >
        <Typography variant="body2">{error}</Typography>
      </Paper>
    );
  }

  return (
    <Paper 
      elevation={3}
      className="file-info-paper"
      sx={{ 
        p: 0, 
        mb: 4, 
        borderRadius: 2,
        overflow: 'hidden',
        transition: 'all 0.3s ease'
      }}
    >
      {/* Header with gradient background */}
      <Box 
        sx={{ 
          p: 2, 
          background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
          color: 'white',
          display: 'flex', 
          alignItems: 'center',
          justifyContent: 'space-between'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center' }}>
          <InfoIcon sx={{ mr: 1.5, fontSize: 28 }} />
          <Typography variant="h6" fontWeight="500">
            Current CSV File Information
          </Typography>
        </Box>
        <Chip 
          label="Active" 
          size="small"
          sx={{ 
            backgroundColor: 'rgba(255, 255, 255, 0.25)', 
            color: 'white',
            fontWeight: 'bold'
          }} 
        />
      </Box>
      
      <Divider />
      
      {/* Content */}
      <CardContent sx={{ p: 3, backgroundColor: '#f8f9fa' }}>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={4}>
            <Box 
              className="file-info-box-item"
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                backgroundColor: 'white',
                p: 1.5,
                borderRadius: 1,
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
              }}
            >
              <InsertDriveFileIcon sx={{ color: '#1976d2', mr: 1.5, fontSize: 24 }} />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  FILE NAME
                </Typography>
                <Typography variant="body1" fontWeight="medium">
                  netspeed.csv
                </Typography>
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <Box 
              className="file-info-box-item"
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                backgroundColor: 'white',
                p: 1.5,
                borderRadius: 1,
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
              }}
            >
              <EventIcon sx={{ color: '#ff9800', mr: 1.5, fontSize: 24 }} />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  CREATED ON
                </Typography>
                <Typography variant="body1" fontWeight="medium">
                  {fileInfo?.date || 'Unknown'}
                </Typography>
              </Box>
            </Box>
          </Grid>
          
          <Grid item xs={12} sm={4}>
            <Box 
              className="file-info-box-item"
              sx={{ 
                display: 'flex', 
                alignItems: 'center',
                backgroundColor: 'white',
                p: 1.5,
                borderRadius: 1,
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
              }}
            >
              <PhoneAndroidIcon sx={{ color: '#4caf50', mr: 1.5, fontSize: 24 }} />
              <Box>
                <Typography variant="caption" color="text.secondary">
                  PHONE ENTRIES
                </Typography>
                <Typography variant="body1" fontWeight="medium">
                  {fileInfo?.line_count.toLocaleString() || '0'} lines
                </Typography>
              </Box>
            </Box>
          </Grid>
        </Grid>
      </CardContent>
    </Paper>
  );
};

export default FileInfoBox;
