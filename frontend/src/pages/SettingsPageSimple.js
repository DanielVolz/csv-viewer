import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  Button,
  Chip,
  Stack,
  Divider,
  Alert,
  IconButton
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Refresh as RefreshIcon,
  Person as PersonIcon,
  ArrowUpward as ArrowUpIcon,
  ArrowDownward as ArrowDownIcon
} from '@mui/icons-material';
import { useSettings } from '../contexts/SettingsContext';

function SettingsPageSimple() {
  const {
    sshUsername,
    columns,
    toggleColumn,
    reorderColumns,
    resetToDefault,
    updateSshUsername
  } = useSettings();

  const [tempSshUsername, setTempSshUsername] = useState(sshUsername);
  const [showSaved, setShowSaved] = useState(false);

  const handleSaveUsername = () => {
    updateSshUsername(tempSshUsername);
    setShowSaved(true);
    setTimeout(() => setShowSaved(false), 3000);
  };

  const handleResetColumns = () => {
    resetToDefault();
    setShowSaved(true);
    setTimeout(() => setShowSaved(false), 3000);
  };

  const moveColumn = (index, direction) => {
    const newIndex = direction === 'up' ? index - 1 : index + 1;
    if (newIndex >= 0 && newIndex < columns.length) {
      reorderColumns(index, newIndex);
    }
  };

  const enabledCount = columns.filter(col => col.enabled).length;

  return (
    <Box sx={{ maxWidth: 'lg', mx: 'auto' }}>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <SettingsIcon sx={{ fontSize: 28, color: 'primary.main' }} />
          <Typography variant="h4" fontWeight={700}>
            Settings
          </Typography>
        </Box>
        <Typography variant="body1" color="text.secondary">
          Configure your SSH username and customize which columns are displayed in the CSV data tables.
        </Typography>
      </Box>

      {/* Success Alert */}
      {showSaved && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Settings saved successfully!
        </Alert>
      )}

      <Stack spacing={4}>
        {/* SSH Username Section */}
        <Paper
          elevation={1}
          sx={{
            p: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider'
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
            <PersonIcon sx={{ color: 'primary.main' }} />
            <Typography variant="h6" fontWeight={600}>
              SSH Configuration
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-end' }}>
            <TextField
              fullWidth
              label="SSH Username"
              variant="outlined"
              value={tempSshUsername}
              onChange={(e) => setTempSshUsername(e.target.value)}
              placeholder="Enter your SSH username"
              helperText="This username will be used for SSH connections to network devices. Click Switch Hostname in tables to open SSH links."
              sx={{ flexGrow: 1 }}
            />
            <Button
              variant="contained"
              onClick={handleSaveUsername}
              disabled={tempSshUsername === sshUsername}
              sx={{ height: '56px', minWidth: '100px' }}
            >
              Save
            </Button>
          </Box>
        </Paper>

        {/* Column Configuration Section */}
        <Paper
          elevation={1}
          sx={{
            p: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider'
          }}
        >
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Box>
              <Typography variant="h6" fontWeight={600} sx={{ mb: 1 }}>
                Column Configuration
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {enabledCount} of {columns.length} columns enabled • Use arrows to reorder • Click to toggle
              </Typography>
            </Box>
            <Button
              variant="outlined"
              startIcon={<RefreshIcon />}
              onClick={handleResetColumns}
              sx={{ minWidth: '140px' }}
            >
              Reset Default
            </Button>
          </Box>

          <Divider sx={{ mb: 3 }} />

          {/* Column Pills with Manual Reordering */}
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              minHeight: '120px',
              p: 2,
              borderRadius: 2,
              border: '2px dashed',
              borderColor: 'divider',
              backgroundColor: theme => theme.palette.mode === 'dark'
                ? 'rgba(255, 255, 255, 0.02)'
                : 'rgba(0, 0, 0, 0.01)'
            }}
          >
            {columns.map((column, index) => (
              <Box
                key={column.id}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 1,
                  borderRadius: 1,
                  backgroundColor: theme => theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.05)'
                    : 'rgba(0, 0, 0, 0.02)',
                  transition: 'all 0.2s ease',
                  '&:hover': {
                    backgroundColor: theme => theme.palette.mode === 'dark'
                      ? 'rgba(255, 255, 255, 0.08)'
                      : 'rgba(0, 0, 0, 0.04)'
                  }
                }}
              >
                {/* Reorder Controls */}
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <IconButton
                    size="small"
                    onClick={() => moveColumn(index, 'up')}
                    disabled={index === 0}
                    sx={{ height: '20px', width: '20px' }}
                  >
                    <ArrowUpIcon fontSize="small" />
                  </IconButton>
                  <IconButton
                    size="small"
                    onClick={() => moveColumn(index, 'down')}
                    disabled={index === columns.length - 1}
                    sx={{ height: '20px', width: '20px' }}
                  >
                    <ArrowDownIcon fontSize="small" />
                  </IconButton>
                </Box>

                {/* Column Chip */}
                <Chip
                  label={column.label}
                  variant={column.enabled ? "filled" : "outlined"}
                  color={column.enabled ? "primary" : "default"}
                  sx={{
                    height: '40px',
                    fontSize: '0.875rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                    userSelect: 'none',
                    flexGrow: 1,
                    justifyContent: 'space-between',
                    transition: 'all 0.2s ease',
                    '&:hover': {
                      transform: 'scale(1.02)',
                      boxShadow: 2
                    }
                  }}
                  onClick={() => toggleColumn(column.id)}
                  deleteIcon={
                    column.enabled ? (
                      <RemoveIcon
                        sx={{
                          fontSize: '18px',
                          '&:hover': { color: 'error.main' }
                        }}
                      />
                    ) : (
                      <AddIcon
                        sx={{
                          fontSize: '18px',
                          '&:hover': { color: 'success.main' }
                        }}
                      />
                    )
                  }
                  onDelete={(e) => {
                    e.stopPropagation();
                    toggleColumn(column.id);
                  }}
                />

                {/* Position indicator */}
                <Typography
                  variant="caption"
                  sx={{
                    minWidth: '20px',
                    textAlign: 'center',
                    color: 'text.secondary',
                    fontWeight: 600
                  }}
                >
                  {index + 1}
                </Typography>
              </Box>
            ))}
          </Box>

          <Box sx={{ mt: 3, p: 2, backgroundColor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              <strong>Instructions:</strong>
            </Typography>
            <Stack spacing={0.5}>
              <Typography variant="body2" color="text.secondary">
                • <strong>Use up/down arrows</strong> to reorder columns
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • <strong>Click</strong> a pill to enable/disable the column
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • <strong>Click + or -</strong> to quickly add/remove columns
              </Typography>
              <Typography variant="body2" color="text.secondary">
                • <strong>Enabled columns</strong> (blue) will appear in data tables
              </Typography>
            </Stack>
          </Box>
        </Paper>

        {/* Current Configuration Preview */}
        <Paper
          elevation={1}
          sx={{
            p: 3,
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider'
          }}
        >
          <Typography variant="h6" fontWeight={600} sx={{ mb: 2 }}>
            Current Configuration Preview
          </Typography>

          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              SSH Username: <strong>{sshUsername || 'Not configured'}</strong>
            </Typography>
            {sshUsername && (
              <Typography variant="caption" color="success.main" sx={{ display: 'block', mt: 0.5 }}>
                ✓ SSH links enabled - Click Switch Hostname in data tables to connect
              </Typography>
            )}
            {!sshUsername && (
              <Typography variant="caption" color="warning.main" sx={{ display: 'block', mt: 0.5 }}>
                ⚠ Configure SSH username to enable SSH links for Switch Hostname
              </Typography>
            )}
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Enabled Columns ({enabledCount}):
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {columns
                .filter(col => col.enabled)
                .map((column, index) => (
                  <Chip
                    key={column.id}
                    label={`${index + 1}. ${column.label}`}
                    size="small"
                    variant="filled"
                    color="primary"
                    sx={{ fontSize: '0.75rem' }}
                  />
                ))}
            </Box>
          </Box>
        </Paper>
      </Stack>
    </Box>
  );
}

export default SettingsPageSimple;