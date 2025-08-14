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
  Alert
} from '@mui/material';
import {
  Settings as SettingsIcon,
  Add as AddIcon,
  Remove as RemoveIcon,
  Refresh as RefreshIcon,
  DragIndicator as DragIcon,
  Save as SaveIcon,
  Person as PersonIcon
} from '@mui/icons-material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSettings } from '../contexts/SettingsContext';

// Sortable column pill component
function SortableColumnPill({ column, onToggle }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: column.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    zIndex: isDragging ? 1000 : 1,
  };

  const chipSx = {
    height: '40px',
    fontSize: '0.875rem',
    fontWeight: 500,
    cursor: 'pointer',
    userSelect: 'none',
    opacity: isDragging ? 0.7 : 1,
    transition: isDragging ? 'none' : 'all 0.2s ease',
    boxShadow: isDragging ? '0 2px 8px rgba(0, 0, 0, 0.25)' : '0 2px 4px rgba(0, 0, 0, 0.1)',
    transform: isDragging ? 'rotate(5deg) scale(1.05)' : 'none',
    '&:hover': {
      transform: isDragging ? 'rotate(5deg) scale(1.05)' : 'scale(1.02)',
      boxShadow: isDragging ? '0 8px 25px rgba(0, 0, 0, 0.15)' : '0 4px 12px rgba(0, 0, 0, 0.15)'
    },
    '& .MuiChip-icon': {
      marginLeft: '8px',
      marginRight: '-4px',
      cursor: 'grab',
      '&:active': { cursor: 'grabbing' }
    },
    '& .MuiChip-deleteIcon': { marginLeft: '4px', marginRight: '8px' },
    ...(column.enabled ? {
      bgcolor: 'primary.main',
      color: 'primary.contrastText',
      borderColor: 'primary.main',
      '& .MuiChip-icon': { color: 'primary.contrastText' },
      '& .MuiChip-deleteIcon': { color: 'primary.contrastText' },
    } : {}),
  };

  return (
    <div ref={setNodeRef} style={style}>
      <Chip
        icon={<DragIcon sx={{ cursor: 'grab' }} {...listeners} {...attributes} />}
        label={column.label}
        variant={column.enabled ? 'filled' : 'outlined'}
        color={column.enabled ? 'primary' : 'default'}
        sx={chipSx}
        onClick={() => onToggle(column.id)}
        deleteIcon={
          column.enabled ? (
            <RemoveIcon sx={{ fontSize: '18px', '&:hover': { color: 'error.main' } }} />
          ) : (
            <AddIcon sx={{ fontSize: '18px', '&:hover': { color: 'success.main' } }} />
          )
        }
        onDelete={(e) => {
          e.stopPropagation();
          onToggle(column.id);
        }}
      />
    </div>
  );
}

function SettingsPageDnd() {
  const {
    sshUsername,
    columns,
    toggleColumn,
    reorderColumns,
    resetToDefault,
    updateSshUsername,
    saveColumns
  } = useSettings();

  const [tempSshUsername, setTempSshUsername] = useState(sshUsername);
  const [showSaved, setShowSaved] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [columnsDirty, setColumnsDirty] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8, // 8px of movement before drag starts
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragStart = () => {
    setIsDragging(true);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    setIsDragging(false);

    if (active.id !== over?.id) {
      const oldIndex = columns.findIndex(col => col.id === active.id);
      const newIndex = columns.findIndex(col => col.id === over.id);
      reorderColumns(oldIndex, newIndex);
      setColumnsDirty(true);
    }
  };

  const handleSaveUsername = () => {
    updateSshUsername(tempSshUsername);
    setShowSaved(true);
    setTimeout(() => setShowSaved(false), 3000);
  };

  const handleResetColumns = () => {
    resetToDefault();
    setShowSaved(true);
    setTimeout(() => setShowSaved(false), 3000);
    setColumnsDirty(false);
  };

  const handleSaveColumns = () => {
    // Explicitly persist current columns
    saveColumns(columns);
    setShowSaved(true);
    setColumnsDirty(false);
    setTimeout(() => setShowSaved(false), 3000);
  };

  const handleToggleColumn = (id) => {
    toggleColumn(id);
    setColumnsDirty(true);
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

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-end', flexWrap: 'nowrap' }}>
            <TextField
              fullWidth
              label="SSH Username"
              variant="outlined"
              value={tempSshUsername}
              onChange={(e) => setTempSshUsername(e.target.value)}
              placeholder="Enter your SSH username"
              sx={{ flexGrow: 1, minWidth: 260 }}
              InputLabelProps={{ shrink: true }}
              InputProps={{
                sx: {
                  height: 48,
                  '& .MuiOutlinedInput-input': {
                    height: 48,
                    lineHeight: '48px',
                    py: 0
                  }
                }
              }}
            />
            <Button
              variant="contained"
              startIcon={<SaveIcon />}
              onClick={handleSaveUsername}
              disabled={tempSshUsername === sshUsername}
              color={tempSshUsername === sshUsername ? 'inherit' : 'primary'}
              sx={{ minWidth: '120px' }}
            >
              Save
            </Button>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
            This username will be used for SSH connections to network devices. Click Switch Hostname in tables to open SSH links.
          </Typography>
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
                {enabledCount} of {columns.length} columns enabled • Drag to reorder • Click to toggle
              </Typography>
            </Box>
            <Stack direction="row" spacing={1.5} alignItems="center">
              <Button
                variant="outlined"
                startIcon={<RefreshIcon />}
                onClick={handleResetColumns}
                sx={{ minWidth: '140px' }}
              >
                Reset Default
              </Button>
              <Button
                variant="contained"
                startIcon={<SaveIcon />}
                onClick={handleSaveColumns}
                disabled={!columnsDirty}
                color={columnsDirty ? 'primary' : 'inherit'}
                sx={{ minWidth: '120px' }}
              >
                Save
              </Button>
            </Stack>
          </Box>

          <Divider sx={{ mb: 3 }} />

          {/* Column Pills with Drag and Drop */}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
          >
            <SortableContext
              items={columns.map(col => col.id)}
              strategy={verticalListSortingStrategy}
            >
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 2,
                  minHeight: '120px',
                  p: 2,
                  borderRadius: 2,
                  border: '2px dashed',
                  borderColor: isDragging ? 'primary.main' : 'divider',
                  backgroundColor: theme => {
                    if (isDragging) {
                      return theme.palette.mode === 'dark'
                        ? 'rgba(59, 130, 246, 0.05)'
                        : 'rgba(59, 130, 246, 0.02)';
                    }
                    return theme.palette.mode === 'dark'
                      ? 'rgba(255, 255, 255, 0.02)'
                      : 'rgba(0, 0, 0, 0.01)';
                  },
                  transition: 'all 0.2s ease'
                }}
              >
                {columns.map((column) => (
                  <SortableColumnPill
                    key={column.id}
                    column={column}
                    onToggle={handleToggleColumn}
                  />
                ))}
              </Box>
            </SortableContext>
          </DndContext>

          <Box sx={{ mt: 3, p: 2, backgroundColor: 'action.hover', borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              <strong>Instructions:</strong>
            </Typography>
            <Stack spacing={0.5}>
              <Typography variant="body2" color="text.secondary">
                • <strong>Drag</strong> the drag handle (⋮⋮) to reorder columns
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

export default SettingsPageDnd;