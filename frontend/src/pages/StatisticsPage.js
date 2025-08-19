import React from 'react';
import { Box, Card, CardContent, Grid, Typography, List, ListItem, ListItemText, Paper, Skeleton, Alert, Autocomplete, TextField, Chip, Accordion, AccordionSummary, AccordionDetails, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Button } from '@mui/material';
import { LineChart } from '@mui/x-charts';
import { alpha } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useSettings } from '../contexts/SettingsContext';

// Heuristic: detect MAC address strings in common formats and exclude from model lists
function isMacLike(value) {
  if (!value) return false;
  const s = String(value).trim();
  // 6 octets with : or - separators (AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF)
  const sep6 = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/;
  // Cisco-style dotted (AABB.CCDD.EEFF)
  const dotted = /^([0-9A-Fa-f]{4}\.){2}([0-9A-Fa-f]{4})$/;
  // Plain 12 hex digits (AABBCCDDEEFF)
  const plain12 = /^[0-9A-Fa-f]{12}$/;
  return sep6.test(s) || dotted.test(s) || plain12.test(s);
}

function StatCard({ title, value, loading, tone = 'primary' }) {
  return (
    <Card
      elevation={0}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 2,
        backgroundColor: (theme) => alpha(theme.palette[tone].main, theme.palette.mode === 'dark' ? 0.12 : 0.06),
        borderLeft: '4px solid',
        borderLeftColor: (theme) => theme.palette[tone].main,
      }}
    >
      <CardContent>
        <Typography variant="overline" sx={{ color: (theme) => theme.palette[tone].main, fontWeight: 600 }}>{title}</Typography>
        {loading ? (
          <Skeleton variant="text" sx={{ fontSize: '2rem', width: 120 }} />
        ) : (
          <Typography variant="h4" sx={{ fontWeight: 700 }}>{value?.toLocaleString?.() ?? value}</Typography>
        )}
      </CardContent>
    </Card>
  );
}

export default function StatisticsPage() {
  const { sshUsername } = useSettings?.() || { sshUsername: '' };
  const makeSshUrl = (host) => {
    if (!host) return null;
    const userPart = sshUsername ? `${encodeURIComponent(sshUsername)}@` : '';
    return `ssh://${userPart}${encodeURIComponent(host)}`;
  };
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [data, setData] = React.useState({
    totalPhones: 0,
    totalSwitches: 0,
    totalLocations: 0,
    totalCities: 0,
    phonesWithKEM: 0,
    phonesByModel: [],
    cities: [],
  });
  // Map 3-letter city code to human name from stats payload
  const cityNameByCode3 = React.useMemo(() => {
    const map = {};
    try {
      (data?.cities || []).forEach(({ code, name }) => {
        const k = String(code || '').slice(0, 3).toUpperCase();
        if (k) map[k] = name || k;
      });
    } catch { }
    return map;
  }, [data?.cities]);
  const [fileMeta, setFileMeta] = React.useState(null);
  // Timeline state (last 31 days)
  const [timeline, setTimeline] = React.useState({ loading: false, error: null, series: [] });
  const [backfillInfo, setBackfillInfo] = React.useState(null);
  const timelineLoadedRef = React.useRef(false);
  // KPI selection for the timeline (controls which series are shown)
  const KPI_DEFS = React.useMemo(() => ([
    { id: 'totalPhones', label: 'Total Phones', color: '#1976d2' },
    { id: 'phonesWithKEM', label: 'Phones with KEM', color: '#2e7d32' },
    { id: 'totalSwitches', label: 'Total Switches', color: '#0288d1' },
    { id: 'totalLocations', label: 'Total Locations', color: '#f57c00' },
    { id: 'totalCities', label: 'Total Cities', color: '#6a1b9a' },
  ]), []);
  // For per-location timeline, exclude Locations/Cities which don't make sense in that context
  const KPI_DEFS_LOC = React.useMemo(() => KPI_DEFS.filter(k => k.id !== 'totalLocations' && k.id !== 'totalCities'), [KPI_DEFS]);
  // Default: exclude the very large 'Total Phones' so other KPIs are readable initially
  const [selectedKpis, setSelectedKpis] = React.useState(() => KPI_DEFS.filter(k => k.id !== 'totalPhones').map(k => k.id));
  const toggleKpi = (id) => {
    setSelectedKpis((prev) => prev.includes(id) ? prev.filter(k => k !== id) : [...prev, id]);
  };

  // Location-specific state
  const [locInput, setLocInput] = React.useState('');
  const [locOptions, setLocOptions] = React.useState([]);
  const [locLoading, setLocLoading] = React.useState(false);
  const [locError, setLocError] = React.useState(null);
  const [locSelected, setLocSelected] = React.useState(null);
  const [locStats, setLocStats] = React.useState({
    query: '',
    mode: '',
    totalPhones: 0,
    totalSwitches: 0,
    phonesWithKEM: 0,
    phonesByModel: [],
    vlanUsage: [],
    switches: [],
    kemPhones: [],
  });
  const [locStatsLoading, setLocStatsLoading] = React.useState(false);
  const [locOpen, setLocOpen] = React.useState(false);
  // Location-specific timeline state
  const [locTimeline, setLocTimeline] = React.useState({ loading: false, error: null, series: [] });
  const locTimelineLoadedKeyRef = React.useRef('');
  const locInputUpper = (locInput || '').trim().toUpperCase();
  const isThreeLetterPrefix = /^[A-Z]{3}$/.test(locInputUpper);
  // Inject synthetic option for prefix mode at the top
  const autoOptions = React.useMemo(() => {
    if (isThreeLetterPrefix) return [locInputUpper, ...(locOptions || [])];
    return locOptions || [];
  }, [isThreeLetterPrefix, locInputUpper, locOptions]);
  const getOptionLabel = (opt) => {
    const s = String(opt || '').toUpperCase();
    if (/^[A-Z]{3}$/.test(s)) {
      const nm = cityNameByCode3[s];
      return nm ? `All locations for ${s} (${nm})` : `All locations for ${s}`;
    }
    if (/^[A-Z]{3}[0-9]{2}$/.test(s)) {
      const nm = cityNameByCode3[s.slice(0, 3)];
      return nm ? `${s} (${nm})` : s;
    }
    return s;
  };

  React.useEffect(() => {
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setLoading(true);
        const r = await fetch('/api/stats/current', { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          setData(json.data || {});
          setFileMeta(json.file || null);
          setError(null);
        } else {
          // Treat missing file as non-fatal informational state
          setData({ totalPhones: 0, totalSwitches: 0, totalLocations: 0, totalCities: 0, phonesWithKEM: 0, phonesByModel: [], cities: [] });
          setFileMeta(json.file || null);
          setError(json.message || 'No statistics available');
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setError('Failed to load statistics');
      } finally {
        if (!abort) setLoading(false);
      }
    })();
    return () => { abort = true; controller.abort(); };
  }, []);

  // Lazy-load timeline when the timeline section comes into view
  const timelineRef = React.useRef(null);
  React.useEffect(() => {
    if (!timelineRef.current || timelineLoadedRef.current) return;
    const el = timelineRef.current;
    const observer = new IntersectionObserver((entries) => {
      const [entry] = entries;
      if (!entry || !entry.isIntersecting || timelineLoadedRef.current) return;
      timelineLoadedRef.current = true;
      let abort = false;
      const controller = new AbortController();
      (async () => {
        try {
          setTimeline((t) => ({ ...t, loading: true, error: null }));
          const r = await fetch('/api/stats/timeline?limit=0', { signal: controller.signal });
          if (!r.ok) throw new Error(`HTTP ${r.status}`);
          const json = await r.json();
          if (abort) return;
          if (json.success) {
            const series = json.series || [];
            if (series.length === 0) {
              setTimeline({ loading: false, error: json.message || 'No timeline snapshots available yet', series: [] });
            } else {
              setTimeline({ loading: false, error: null, series });
            }
          } else {
            setTimeline({ loading: false, error: json.message || 'No timeline available', series: [] });
          }
        } catch (e) {
          if (e.name === 'AbortError') return;
          setTimeline({ loading: false, error: 'Failed to load timeline', series: [] });
        }
      })();
      return () => { abort = true; controller.abort(); };
    }, { threshold: 0.2 });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const triggerBackfill = React.useCallback(async () => {
    try {
      setBackfillInfo('Starting snapshot backfill…');
      // Fire-and-forget both; errors are non-fatal here
      await Promise.allSettled([
        fetch('/api/search/index/backfill-stats', { method: 'POST' }),
        fetch('/api/search/index/backfill-locations', { method: 'POST' }),
      ]);
      setBackfillInfo('Backfill started. Data will appear shortly.');
    } catch (_) {
      setBackfillInfo('Failed to trigger backfill. Check backend logs.');
    }
  }, []);

  // Debounced fetch for location options
  React.useEffect(() => {
    let abort = false;
    const controller = new AbortController();
    const h = setTimeout(async () => {
      try {
        setLocLoading(true);
        setLocError(null);
        const q = encodeURIComponent(locInput.trim());
        // Request all locations (no server-side limit) so the dropdown can show everything with scroll
        const r = await fetch(`/api/stats/locations?q=${q}&limit=0`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        const options = (json?.options || []).filter((o) => /^[A-Z]{3}[0-9]{2}$/.test(String(o)));
        setLocOptions(options);
      } catch (e) {
        if (e.name === 'AbortError') return;
        setLocError('Failed to load locations');
      } finally {
        if (!abort) setLocLoading(false);
      }
    }, 350);
    return () => { abort = true; controller.abort(); clearTimeout(h); };
  }, [locInput]);

  // Fetch stats for selected location
  React.useEffect(() => {
    if (!locSelected) return;
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setLocStatsLoading(true);
        setLocError(null);
        const q = encodeURIComponent(locSelected);
        const r = await fetch(`/api/stats/by_location?q=${q}`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          setLocStats(json.data || {});
        } else {
          setLocStats({ query: locSelected, mode: '', totalPhones: 0, totalSwitches: 0, phonesWithKEM: 0, phonesByModel: [], vlanUsage: [], switches: [], kemPhones: [] });
          setLocError(json.message || 'No statistics for this location');
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setLocError('Failed to load location statistics');
      } finally {
        if (!abort) setLocStatsLoading(false);
      }
    })();
    return () => { abort = true; controller.abort(); };
  }, [locSelected]);

  // Fetch per-location timeline whenever the selected location changes
  React.useEffect(() => {
    if (!locSelected) return;
    const key = String(locSelected).toUpperCase();
    if (locTimelineLoadedKeyRef.current === key && (locTimeline.series || []).length) return;
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setLocTimeline((t) => ({ ...t, loading: true, error: null }));
        const r = await fetch(`/api/stats/timeline/by_location?q=${encodeURIComponent(locSelected)}&limit=0`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          setLocTimeline({ loading: false, error: null, series: json.series || [] });
          locTimelineLoadedKeyRef.current = key;
        } else {
          setLocTimeline({ loading: false, error: json.message || 'No timeline available for this location', series: [] });
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setLocTimeline({ loading: false, error: 'Failed to load location timeline', series: [] });
      }
    })();
    return () => { abort = true; controller.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locSelected]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 2 }}>
        <Typography variant="h5" fontWeight={700}>Statistics</Typography>
        {fileMeta?.date && (
          <Typography variant="body2" color="text.secondary">from {String(fileMeta.date).slice(0, 10)}</Typography>
        )}
      </Box>

      {error && (
        <Alert severity="info" variant="outlined">{error}</Alert>
      )}

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>General Statistics</Typography>
        <Grid container spacing={2}>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Phones" value={data.totalPhones} loading={loading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="info" title="Total Switches" value={data.totalSwitches} loading={loading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Total Locations" value={data.totalLocations} loading={loading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="secondary" title="Total Cities" value={data.totalCities} loading={loading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={data.phonesWithKEM} loading={loading} /></Grid>
        </Grid>
        {/* Cities enumeration disabled (debug-only); keeping Total Cities stat above */}
      </Paper>

      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.secondary.main}`, backgroundColor: (t) => alpha(t.palette.secondary.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'secondary.main' }}>Phones by Model</Typography>
        {loading ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} variant="rectangular" height={28} />
            ))}
          </Box>
        ) : (
          <List dense>
            {(data.phonesByModel || [])
              .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
              .map(({ model, count }) => {
                const label = String(model);
                const lower = label.toLowerCase();
                let color = 'default';
                if (lower.includes('kem')) color = 'success';
                else if (lower.includes('conference')) color = 'info';
                else if (lower.includes('wireless')) color = 'warning';
                else color = 'secondary';
                return (
                  <ListItem key={model} sx={{ py: 0.5 }}>
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                          <Chip label={label} size="small" color={color} variant={color === 'default' ? 'outlined' : 'filled'} />
                          <Typography variant="body2" fontWeight={700}>{Number(count || 0).toLocaleString()}</Typography>
                        </Box>
                      }
                    />
                  </ListItem>
                );
              })}
          </List>
        )}
      </Paper>

      {/* Statistics by Location */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.info.main}`, backgroundColor: (t) => alpha(t.palette.info.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'info.main' }}>Statistics by Location</Typography>
        <Box sx={{ maxWidth: 520, mb: 2 }}>
          <Autocomplete
            options={autoOptions}
            loading={locLoading}
            value={locSelected}
            freeSolo
            open={locOpen}
            onOpen={() => setLocOpen(true)}
            onClose={() => setLocOpen(false)}
            getOptionLabel={getOptionLabel}
            // Keep popup size fixed and make options scrollable
            slotProps={{
              paper: { sx: { maxHeight: 320, overflowY: 'auto' } },
              listbox: { sx: { maxHeight: 280, overflowY: 'auto' } },
            }}
            ListboxProps={{
              style: { maxHeight: 280, overflowY: 'auto' },
            }}
            onChange={(_, val) => {
              if (typeof val === 'string') {
                const s = val.trim().toUpperCase();
                if (/^[A-Z]{3}$/.test(s) || /^[A-Z]{3}[0-9]{2}$/.test(s)) {
                  setLocSelected(s);
                }
              } else {
                setLocSelected(val);
              }
            }}
            inputValue={locInput}
            onInputChange={(_, val) => {
              setLocInput(val);
            }}
            filterOptions={(x) => x} // server-side filtering
            renderInput={(params) => (
              <TextField
                {...params}
                label="Select Location"
                placeholder="Type 3 letters (ABC) or code (ABC01)"
                size="small"
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = (e.target.value || '').trim().toUpperCase();
                    if (/^[A-Z]{3}$/.test(val) || /^[A-Z]{3}[0-9]{2}$/.test(val)) {
                      setLocSelected(val);
                    } else if (Array.isArray(locOptions) && locOptions.includes(val)) {
                      setLocSelected(val);
                    }
                    setLocOpen(false);
                    if (e.target && typeof e.target.blur === 'function') {
                      e.target.blur();
                    }
                  }
                }}
              />
            )}
          />
          {locError && (
            <Box sx={{ mt: 1 }}>
              <Alert severity="info" variant="outlined">{locError}</Alert>
            </Box>
          )}
        </Box>

        <Grid container spacing={2} sx={{ mb: 1 }}>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Phones" value={locStats.totalPhones} loading={locStatsLoading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="info" title="Total Switches" value={locStats.totalSwitches} loading={locStatsLoading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={locStats.phonesWithKEM} loading={locStatsLoading} /></Grid>
        </Grid>

        {locStats?.mode === 'prefix' && locStats?.query && (
          <Typography variant="caption" color="text.secondary">
            Aggregated across all sites starting with {locStats.query} (e.g., {locStats.query}01, {locStats.query}02, ...)
          </Typography>
        )}

        {/* Location-specific timeline (last 31 days) */}
        {locSelected && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: 'text.secondary' }}>
              Timeline for {locSelected} ({(locTimeline.series || []).length} days)
            </Typography>
            {/* KPI selector (shares state with global timeline; excludes Locations/Cities) */}
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
              {KPI_DEFS_LOC.map((k) => {
                const selected = selectedKpis.includes(k.id);
                return (
                  <Chip
                    key={k.id}
                    label={k.label}
                    size="small"
                    color={selected ? 'success' : 'default'}
                    variant={selected ? 'filled' : 'outlined'}
                    onClick={() => toggleKpi(k.id)}
                  />
                );
              })}
            </Box>
            {locTimeline.loading ? (
              <Skeleton variant="rectangular" height={220} />
            ) : locTimeline.error ? (
              <Alert severity="info" variant="outlined">{locTimeline.error}</Alert>
            ) : (
              <Box sx={{ width: '100%', overflowX: 'auto' }}>
                {selectedKpis.length === 0 ? (
                  <Alert severity="info" variant="outlined">Select at least one KPI to display.</Alert>
                ) : (
                  <LineChart
                    height={240}
                    xAxis={[{ data: (locTimeline.series || []).map((p) => (p.date ? String(p.date).slice(5) : p.file)), scaleType: 'point' }]}
                    series={KPI_DEFS_LOC.filter(k => selectedKpis.includes(k.id)).map((k) => ({
                      id: k.id,
                      label: k.label,
                      color: k.color,
                      data: (locTimeline.series || []).map((p) => p.metrics?.[k.id] || 0),
                    }))}
                    margin={{ left: 40, right: 20, top: 56, bottom: 20 }}
                    slotProps={{
                      legend: {
                        position: { vertical: 'top', horizontal: 'middle' },
                        direction: 'row',
                        itemGap: 16,
                      },
                    }}
                    sx={{ minWidth: 520 }}
                  />
                )}
              </Box>
            )}
          </Box>
        )}

        {/* Additional per-location details */}
        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2} sx={{ mt: 0 }}>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: 'secondary.main' }}>Phones by Model</Typography>
              {locStatsLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={28} />
                  ))}
                </Box>
              ) : (
                <List dense>
                  {(locStats.phonesByModel || [])
                    .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                    .map(({ model, count }) => (
                      <ListItem key={model} sx={{ py: 0.5 }}>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                              <Typography variant="body2" color="text.secondary">{model}</Typography>
                              <Typography variant="body2" fontWeight={600}>{Number(count || 0).toLocaleString()}</Typography>
                            </Box>
                          }
                        />
                      </ListItem>
                    ))}
                </List>
              )}
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: 'primary.main' }}>VLAN Usage</Typography>
              {locStatsLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={28} />
                  ))}
                </Box>
              ) : (
                <List dense>
                  {(locStats.vlanUsage || []).map(({ vlan, count }) => {
                    const vLabel = String(vlan ?? '').trim();
                    const lower = vLabel.toLowerCase();
                    let color = 'default';
                    let variant = 'outlined';
                    if (lower.includes('active')) { color = 'success'; variant = 'filled'; }
                    else if (lower.includes('voice') || lower.includes('voip')) { color = 'secondary'; }
                    else if (lower.includes('data')) { color = 'primary'; }
                    else if (lower.includes('mgmt') || lower.includes('management')) { color = 'warning'; }
                    else if (lower.includes('guest') || lower.includes('visitor')) { color = 'info'; }
                    return (
                      <ListItem key={`vlan-${vlan}`} sx={{ py: 0.5 }}>
                        <ListItemText
                          primary={
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                              <Chip label={vLabel} size="small" color={color} variant={variant} />
                              <Typography variant="body2" fontWeight={700}>{Number(count || 0).toLocaleString()}</Typography>
                            </Box>
                          }
                        />
                      </ListItem>
                    );
                  })}
                </List>
              )}
            </Grid>
          </Grid>
          <Accordion disableGutters elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' }, mt: 2, mb: 1, backgroundColor: (t) => alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.04 : 0.03) }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={700} color="primary.main">
                Switches at this Location {locStats.totalSwitches?.toLocaleString?.() ?? locStats.totalSwitches}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              {locStatsLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={24} />
                  ))}
                </Box>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Switch</TableCell>
                        <TableCell>VLAN</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {((locStats.switchDetails && locStats.switchDetails.length > 0) ? locStats.switchDetails : (locStats.switches || []).map((s) => ({ hostname: s, vlanCount: 0, vlans: [] }))).map((sw) => (
                        <TableRow key={sw.hostname} hover>
                          <TableCell sx={{ whiteSpace: 'nowrap' }}>
                            <Tooltip arrow placement="top" title={`Open SSH ${sshUsername ? `${sshUsername}@` : ''}${sw.hostname}`}>
                              <a href={makeSshUrl(sw.hostname)} style={{ textDecoration: 'none' }}>{sw.hostname}</a>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            {sw.vlans && sw.vlans.length > 0 ? (
                              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                                {sw.vlans.map(({ vlan, count }) => {
                                  const label = String(vlan ?? '').trim();
                                  const lower = label.toLowerCase();
                                  let color = 'default';
                                  let variant = 'outlined';
                                  if (lower.includes('active')) { color = 'success'; variant = 'filled'; }
                                  else if (lower.includes('voice') || lower.includes('voip')) { color = 'secondary'; }
                                  else if (lower.includes('data')) { color = 'primary'; }
                                  else if (lower.includes('mgmt') || lower.includes('management')) { color = 'warning'; }
                                  else if (lower.includes('guest') || lower.includes('visitor')) { color = 'info'; }
                                  else if (lower.includes('inactive') || lower.includes('down') || lower.includes('disabled')) { color = 'default'; variant = 'outlined'; }
                                  return (
                                    <Chip
                                      key={`${sw.hostname}-vlan-${vlan}`}
                                      size="small"
                                      label={`${label}: ${count}`}
                                      color={color}
                                      variant={variant}
                                    />
                                  );
                                })}
                              </Box>
                            ) : (
                              <Typography variant="body2" color="text.secondary">—</Typography>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </AccordionDetails>
          </Accordion>

          <Accordion disableGutters elevation={0} sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' }, backgroundColor: (t) => alpha(t.palette.success.light, t.palette.mode === 'dark' ? 0.04 : 0.03) }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={700} color="success.main">
                Phones with KEM at this Location {locStats.phonesWithKEM?.toLocaleString?.() ?? locStats.phonesWithKEM}
              </Typography>
            </AccordionSummary>
            <AccordionDetails>
              {locStatsLoading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={24} />
                  ))}
                </Box>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1 }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>IP Address</TableCell>
                        <TableCell>MAC Address</TableCell>
                        <TableCell>Switch Hostname</TableCell>
                        <TableCell align="right">KEMs</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(locStats.kemPhones || []).map((p, idx) => {
                        const key = (p['MAC Address'] || p['IP Address'] || String(idx));
                        const mac = p['MAC Address'];
                        const ip = p['IP Address'];
                        const kem1 = (p['KEM'] || '').trim();
                        const kem2 = (p['KEM 2'] || '').trim();
                        const kemCount = (kem1 ? 1 : 0) + (kem2 ? 1 : 0);
                        return (
                          <TableRow key={key} sx={{ '&:nth-of-type(odd)': { backgroundColor: 'action.hover' } }} hover>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                              {ip ? (
                                <Tooltip arrow placement="top" title={`Open http://${ip}`}>
                                  <a
                                    href={`http://${encodeURIComponent(ip)}`}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{ textDecoration: 'none' }}
                                  >
                                    {ip}
                                  </a>
                                </Tooltip>
                              ) : 'n/a'}
                            </TableCell>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                              {mac ? (<a href={`/?q=${encodeURIComponent(mac)}`} style={{ textDecoration: 'none' }}>{mac}</a>) : 'n/a'}
                            </TableCell>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                              {p['Switch Hostname'] ? (
                                <Tooltip arrow placement="top" title={`Open SSH ${sshUsername ? `${sshUsername}@` : ''}${p['Switch Hostname']}`}>
                                  <a href={makeSshUrl(p['Switch Hostname'])} style={{ textDecoration: 'none' }}>
                                    {p['Switch Hostname']}
                                  </a>
                                </Tooltip>
                              ) : ''}
                            </TableCell>
                            <TableCell align="right">{kemCount}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </AccordionDetails>
          </Accordion>
        </Box>

        {/* Only summary metrics per location as requested */}
      </Paper>

      {/* Timeline in separate section */}
      <Paper ref={timelineRef} variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>Timeline ({(timeline.series || []).length} days)</Typography>
        {/* KPI selector */}
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
          {KPI_DEFS.map((k) => {
            const selected = selectedKpis.includes(k.id);
            return (
              <Chip
                key={k.id}
                label={k.label}
                size="small"
                color={selected ? 'success' : 'default'}
                variant={selected ? 'filled' : 'outlined'}
                onClick={() => toggleKpi(k.id)}
              />
            );
          })}
        </Box>
        {timeline.loading ? (
          <Skeleton variant="rectangular" height={220} />
        ) : timeline.error ? (
          <Alert severity="info" variant="outlined">{timeline.error}</Alert>
        ) : (
          <Box sx={{ width: '100%', overflowX: 'auto' }}>
            {selectedKpis.length === 0 ? (
              <Alert severity="info" variant="outlined">Select at least one KPI to display.</Alert>
            ) : (
              <LineChart
                height={260}
                xAxis={[{ data: (timeline.series || []).map((p) => (p.date ? String(p.date).slice(5) : p.file)), scaleType: 'point' }]}
                series={KPI_DEFS.filter(k => selectedKpis.includes(k.id)).map((k) => ({
                  id: k.id,
                  label: k.label,
                  color: k.color,
                  data: (timeline.series || []).map((p) => p.metrics?.[k.id] || 0),
                }))}
                margin={{ left: 40, right: 20, top: 56, bottom: 20 }}
                slotProps={{
                  legend: {
                    position: { vertical: 'top', horizontal: 'middle' },
                    direction: 'row',
                    itemGap: 16,
                  },
                }}
                sx={{ minWidth: 520 }}
              />
            )}
          </Box>
        )}
        {timeline.error && (
          <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
            <Button size="small" variant="outlined" onClick={triggerBackfill}>Backfill snapshots</Button>
            {backfillInfo && (
              <Typography variant="caption" color="text.secondary">{backfillInfo}</Typography>
            )}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
