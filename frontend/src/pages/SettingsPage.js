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
  Person as PersonIcon
} from '@mui/icons-material';
// Import DnD kit components
let DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors;
let SortableContext, sortableKeyboardCoordinates, verticalListSortingStrategy;
let useSortable, CSS;

try {
  const dndCore = require('@dnd-kit/core');
  const dndSortable = require('@dnd-kit/sortable');
  const dndUtilities = require('@dnd-kit/utilities');

  DndContext = dndCore.DndContext;
  closestCenter = dndCore.closestCenter;
  KeyboardSensor = dndCore.KeyboardSensor;
  PointerSensor = dndCore.PointerSensor;
  useSensor = dndCore.useSensor;
  useSensors = dndCore.useSensors;

  SortableContext = dndSortable.SortableContext;
  sortableKeyboardCoordinates = dndSortable.sortableKeyboardCoordinates;
  verticalListSortingStrategy = dndSortable.verticalListSortingStrategy;
  useSortable = dndSortable.useSortable;

  CSS = dndUtilities.CSS;
} catch (error) {
  console.warn('DnD Kit not available, falling back to manual reordering');
}
import { useSettings } from '../contexts/SettingsContext';

// Sortable column pill component
function SortableColumnPill({ column, onToggle, onRemove }) {
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

  return (
    <div ref={setNodeRef} style={style}>
      <Chip
        icon={<DragIcon sx={{ cursor: 'grab' }} {...listeners} {...attributes} />}
        label={column.label}
        variant={column.enabled ? "filled" : "outlined"}
        color={column.enabled ? "primary" : "default"}
        sx={{
          height: '40px',
          fontSize: '0.875rem',
          fontWeight: 500,
          cursor: 'pointer',
          userSelect: 'none',
          opacity: isDragging ? 0.5 : 1,
          transition: 'all 0.2s ease',
          '&:hover': {
            transform: isDragging ? 'none' : 'scale(1.02)',
            boxShadow: 2
          },
          '& .MuiChip-icon': {
            marginLeft: '8px',
            marginRight: '-4px'
          },
          '& .MuiChip-deleteIcon': {
            marginLeft: '4px',
            marginRight: '8px'
          }
        }}
        onClick={() => onToggle(column.id)}
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
          onToggle(column.id);
        }}
      />
    </div>
  );
}

function SettingsPage() {
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

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over?.id) {
      const oldIndex = columns.findIndex(col => col.id === active.id);
      const newIndex = columns.findIndex(col => col.id === over.id);
      reorderColumns(oldIndex, newIndex);
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
              helperText="This username will be used for SSH connections to network devices"
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
                {enabledCount} of {columns.length} columns enabled • Drag to reorder • Click to toggle
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

          {/* Column Pills with Drag and Drop */}
          <DndContext
            sensors={sensors}
            collisionDetection={closestCenter}
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
                  borderColor: 'divider',
                  backgroundColor: theme => theme.palette.mode === 'dark'
                    ? 'rgba(255, 255, 255, 0.02)'
                    : 'rgba(0, 0, 0, 0.01)'
                }}
              >
                {columns.map((column) => (
                  <SortableColumnPill
                    key={column.id}
                    column={column}
                    onToggle={toggleColumn}
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

export default SettingsPage;