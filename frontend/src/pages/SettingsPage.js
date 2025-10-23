import React, { useEffect, useState } from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Alert,
  Box,
  Button,
  Chip,
  Divider,
  Paper,
  Stack,
  TextField,
  Typography
} from '@mui/material';
import {
  CheckCircleRounded as CheckCircleIcon,
  DragIndicator as DragIcon,
  ExpandMore as ExpandMoreIcon,
  Person as PersonIcon,
  Refresh as RefreshIcon,
  Settings as SettingsIcon
} from '@mui/icons-material';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors
} from '@dnd-kit/core';
import {
  horizontalListSortingStrategy,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useSettings } from '../contexts/SettingsContext';

function SortableEnabledChip({ column }) {
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
    <div ref={setNodeRef} style={{ ...style, display: 'inline-flex' }}>
      <Chip
        icon={<DragIcon sx={{ cursor: 'grab' }} {...listeners} {...attributes} />}
        label={column.label}
        variant="filled"
        sx={{
          fontWeight: 500,
          height: 36,
          cursor: 'grab',
          opacity: isDragging ? 0.6 : 1,
          bgcolor: theme => theme.palette.success.main,
          color: theme => theme.palette.success.contrastText,
          '& .MuiChip-icon': {
            marginLeft: '8px',
            marginRight: '-4px',
            color: theme => theme.palette.success.contrastText
          }
        }}
      />
    </div>
  );
}

function SettingsPage() {
  const {
    sshUsername,
    columns,
    enabledColumns,
    categorizedColumns,
    toggleColumn,
    reorderColumns,
    resetToDefault,
    updateSshUsername
  } = useSettings();

  const [tempSshUsername, setTempSshUsername] = useState(sshUsername);
  const [showSaved, setShowSaved] = useState(false);
  const [expandedCategories, setExpandedCategories] = useState({});
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  useEffect(() => {
    setExpandedCategories(() => {
      const next = {};
      categorizedColumns.forEach((category) => {
        next[category.id] = true;
      });
      return next;
    });
  }, [categorizedColumns]);

  const handleEnabledDragEnd = (event) => {
    if (!event || !event.active) return;
    const { active, over } = event;
    if (!over || active.id === over.id) {
      return;
    }

    const fromIndex = columns.findIndex(col => col.id === active.id);
    let toIndex = columns.findIndex(col => col.id === over.id);

    if (fromIndex === -1) {
      return;
    }

    if (toIndex === -1) {
      toIndex = columns.length - 1;
    }

    if (fromIndex !== toIndex) {
      reorderColumns(fromIndex, toIndex);
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

  const handleCategoryToggle = (categoryId) => (_event, isExpanded) => {
    setExpandedCategories(prev => ({
      ...prev,
      [categoryId]: isExpanded
    }));
  };

  const enabledCount = enabledColumns.length;

  return (
    <Box sx={{ maxWidth: 'lg', mx: 'auto' }}>
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

      {showSaved && (
        <Alert severity="success" sx={{ mb: 3 }}>
          Settings saved successfully!
        </Alert>
      )}

      <Stack spacing={4}>
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

          <Box
            sx={{
              display: 'grid',
              gap: 2,
              alignItems: { xs: 'stretch', sm: 'start' },
              gridTemplateColumns: { xs: '1fr', sm: 'minmax(0, 1fr) auto' }
            }}
          >
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
              sx={{
                height: { xs: 48, sm: 56 },
                minWidth: 120,
                justifySelf: { xs: 'stretch', sm: 'flex-start' },
                alignSelf: { xs: 'stretch', sm: 'start' }
              }}
            >
              Save
            </Button>
          </Box>
        </Paper>

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
                {enabledCount} of {columns.length} columns enabled • Drag to reorder enabled columns above • Toggle columns within categories below
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

          <Box sx={{ mb: 3 }}>
            <Typography variant="subtitle1" fontWeight={600} sx={{ mb: 1 }}>
              Enabled Columns
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Drag to adjust the order used across the application. Enable or disable columns inside the categories below.
            </Typography>

            {enabledColumns.length === 0 ? (
              <Paper
                variant="outlined"
                sx={{
                  p: 2,
                  borderStyle: 'dashed',
                  borderRadius: 2,
                  textAlign: 'center'
                }}
              >
                <Typography variant="body2" color="text.secondary">
                  No columns enabled. Activate columns within the categories to manage their order here.
                </Typography>
              </Paper>
            ) : (
              <Box
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 1.5,
                  p: 2,
                  borderRadius: 2,
                  border: '1px dashed',
                  borderColor: 'divider',
                  backgroundColor: theme => theme.palette.mode === 'dark'
                    ? 'rgba(255,255,255,0.03)'
                    : 'rgba(0,0,0,0.02)'
                }}
              >
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleEnabledDragEnd}
                >
                  <SortableContext
                    items={enabledColumns.map(col => col.id)}
                    strategy={horizontalListSortingStrategy}
                  >
                    {enabledColumns.map((column) => (
                      <SortableEnabledChip key={column.id} column={column} />
                    ))}
                  </SortableContext>
                </DndContext>
              </Box>
            )}
          </Box>

          <Divider sx={{ mb: 3 }} />

          <Stack spacing={2}>
            {categorizedColumns.map((category) => {
              const enabledInCategory = category.columns.filter(column => column.enabled).length;
              return (
                <Accordion
                  key={category.id}
                  expanded={expandedCategories[category.id] ?? true}
                  onChange={handleCategoryToggle(category.id)}
                  disableGutters
                  sx={{
                    border: '1px solid',
                    borderColor: 'divider',
                    borderRadius: 2,
                    '&:before': { display: 'none' }
                  }}
                >
                  <AccordionSummary
                    expandIcon={<ExpandMoreIcon />}
                    sx={{ px: 2, py: 1.5 }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexGrow: 1 }}>
                      <Typography variant="subtitle1" fontWeight={600}>
                        {category.label}
                      </Typography>
                      <Chip
                        size="small"
                        label={`${enabledInCategory}/${category.columns.length} enabled`}
                        color={enabledInCategory > 0 ? 'primary' : 'default'}
                        variant={enabledInCategory > 0 ? 'filled' : 'outlined'}
                        sx={{ fontWeight: 500 }}
                      />
                    </Box>
                  </AccordionSummary>
                  <AccordionDetails sx={{ px: 2, pb: 2 }}>
                    <Box
                      sx={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 1.5
                      }}
                    >
                      {category.columns.map((column) => (
                        <Chip
                          key={column.id}
                          label={column.label}
                          onClick={() => toggleColumn(column.id)}
                          icon={column.enabled ? <CheckCircleIcon sx={{ fontSize: 18 }} /> : undefined}
                          color={column.enabled ? 'success' : 'default'}
                          variant={column.enabled ? 'filled' : 'outlined'}
                          sx={{
                            cursor: 'pointer',
                            fontWeight: 500,
                            ...(column.enabled ? {
                              bgcolor: theme => theme.palette.success.main,
                              color: theme => theme.palette.success.contrastText,
                              '& .MuiChip-icon': { color: theme => theme.palette.success.contrastText }
                            } : {}),
                            ...(!column.enabled ? {
                              bgcolor: 'transparent'
                            } : {}),
                            '&:hover': {
                              transform: 'translateY(-1px)',
                              boxShadow: 1
                            }
                          }}
                        />
                      ))}
                    </Box>
                  </AccordionDetails>
                </Accordion>
              );
            })}
          </Stack>
        </Paper>

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
            {sshUsername ? (
              <Typography
                variant="caption"
                color="success.main"
                sx={{ display: 'block', mt: 0.5 }}
              >
                ✓ SSH links enabled — click Switch Hostname in data tables to connect automatically.
              </Typography>
            ) : (
              <Typography
                variant="caption"
                color="warning.main"
                sx={{ display: 'block', mt: 0.5 }}
              >
                ⚠ Configure your SSH username to enable direct Switch Hostname connections.
              </Typography>
            )}
          </Box>

          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              Enabled Columns ({enabledCount}):
            </Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
              {enabledColumns.map((column, index) => (
                <Chip
                  key={column.id}
                  label={`${index + 1}. ${column.label}`}
                  size="small"
                  variant="outlined"
                  color="default"
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