import React, { useState, useEffect } from 'react';
import { 
  Card,
  CardContent,
  Typography, 
  Box, 
  CircularProgress, 
  Avatar,
  Chip,
  Stack,
  alpha,
  Fade,
  LinearProgress,
  IconButton,
  Tooltip,
  Divider,
  Paper
} from '@mui/material';
import {
  Info,
  Storage,
  Schedule,
  DataUsage,
  TrendingUp,
  Speed,
  Refresh,
  CheckCircle,
  Warning,
  Analytics,
  CloudSync
} from '@mui/icons-material';
import axios from 'axios';

const FileInfoBox = ({ compact = false }) => {
  const [fileInfo, setFileInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchFileInfo = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/files/netspeed_info');
      const data = response.data;
      
      if (data.success) {
        setFileInfo(data);
        setError(null);
      } else {
        setError(data.message || 'Failed to fetch file information');
      }
    } catch (err) {
      setError('Error fetching file information');
      console.error('Error fetching file info:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchFileInfo();
    setRefreshing(false);
  };

  useEffect(() => {
    fetchFileInfo();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchFileInfo, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <Fade in>
        <Card 
          elevation={0}
          sx={{
            background: theme => alpha(theme.palette.background.paper, 0.8),
            backdropFilter: 'blur(20px)',
            border: theme => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
            borderRadius: 4,
            p: 3,
            textAlign: 'center'
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
          background: theme => `linear-gradient(135deg, ${alpha(theme.palette.error.main, 0.1)}, ${alpha(theme.palette.error.main, 0.05)})`,
          border: theme => `1px solid ${alpha(theme.palette.error.main, 0.2)}`,
          borderRadius: 4
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
              background: theme => alpha(theme.palette.error.main, 0.1),
              '&:hover': {
                background: theme => alpha(theme.palette.error.main, 0.2),
              }
            }}
          >
            <Refresh />
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
            <Chip
              label="Active"
              color="success"
              size="small"
              variant="outlined"
            />
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
        mb: 4
      }}
    >
      <CardContent sx={{ p: 3 }}>
        {/* Header */}
        <Box sx={{ 
          display: 'flex', 
          alignItems: 'center',
          justifyContent: 'space-between',
          mb: 3
        }}>
          <Typography variant="h6" fontWeight={600}>
            Current File Information
          </Typography>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <Chip
              label="Active"
              color="success"
              size="small"
              variant="outlined"
            />
            <IconButton
              onClick={handleRefresh}
              disabled={refreshing}
              size="small"
            >
              {refreshing ? <CircularProgress size={16} /> : <Refresh fontSize="small" />}
            </IconButton>
          </Box>
        </Box>

        {/* Simple Stats Grid */}
        <Box sx={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
          gap: 2 
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
      </CardContent>
    </Card>
  );
};

export default FileInfoBox;