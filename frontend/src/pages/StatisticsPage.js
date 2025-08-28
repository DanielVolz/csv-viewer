import React from 'react';
import { Box, Card, CardContent, Grid, Typography, List, ListItem, ListItemText, Paper, Skeleton, Alert, Autocomplete, TextField, Chip, Accordion, AccordionSummary, AccordionDetails, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Button } from '@mui/material';
import { LineChart } from '@mui/x-charts';
import { alpha } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Terminal from '@mui/icons-material/Terminal';
import { toast } from 'react-toastify';
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

// Helper: copy to clipboard
const copyToClipboard = async (text) => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(String(text));
      return true;
    }
  } catch (_) { }
  try {
    const ta = document.createElement('textarea');
    ta.value = String(text);
    ta.setAttribute('readonly', '');
    ta.style.position = 'absolute';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return !!ok;
  } catch (_) {
    return false;
  }
};

// Helper: convert switch port to Cisco format (like DataTable)
function convertToCiscoFormat(port) {
  const p = (port || '').toString().trim();
  if (!p) return '';
  // Examples: Gi1/0/1, Te1/1/48, Fa0/1, TenGigabitEthernet1/0/1 etc.
  const map = {
    'GigabitEthernet': 'Gi',
    'TenGigabitEthernet': 'Te',
    'FastEthernet': 'Fa',
    'TwoGigabitEthernet': 'Tw',
    'FortyGigabitEthernet': 'Fo',
    'HundredGigE': 'Hu'
  };
  for (const k of Object.keys(map)) {
    if (p.startsWith(k)) return p.replace(k, map[k]);
  }
  return p;
}

// Helper: unified copy toast like search page
const showCopyToast = (label, value, opts = {}) => {
  const s = String(value ?? '');
  const display = s.length > 48 ? `${s.slice(0, 48)}…` : s;
  toast.success(`📋 ${label}: ${display}`,
    { autoClose: 1500, pauseOnHover: false, ...opts }
  );
};

export default function StatisticsPage() {
  const { sshUsername, navigateToSettings, getStatisticsPrefs, saveStatisticsPrefs } = useSettings?.() || { sshUsername: '' };
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
  const statsHydratedRef = React.useRef(false);
  // Timeline state (configurable days)
  const [timeline, setTimeline] = React.useState({ loading: false, error: null, series: [] });
  const [backfillInfo, setBackfillInfo] = React.useState(null);
  const [timelineDays, setTimelineDays] = React.useState(0); // 0 = full history by default
  const timelineLimitRef = React.useRef(0);
  // Top locations aggregate timeline state
  const [topCount, setTopCount] = React.useState(10);
  const [topExtras, setTopExtras] = React.useState('');
  const [topDays, setTopDays] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const v = saved.statistics?.topDays;
      if (Number.isFinite(v)) return Math.max(0, v);
    } catch { /* ignore */ }
    return 0; // default all days
  });
  const [topTimeline, setTopTimeline] = React.useState({ loading: false, error: null, dates: [], keys: [], seriesByKey: {}, mode: 'per_key' });
  const [topLoadedKey, setTopLoadedKey] = React.useState('');
  const [topSelectedKeys, setTopSelectedKeys] = React.useState([]);
  const [topKpi, setTopKpi] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const s = saved.statistics?.topKpi;
      if (typeof s === 'string' && s) return s;
    } catch { /* ignore */ }
    return 'totalPhones';
  });
  const TOP_KPI_DEFS = React.useMemo(() => ([
    { id: 'totalPhones', label: 'Total Phones', color: '#1976d2' },
    { id: 'phonesWithKEM', label: 'Phones with KEM', color: '#2e7d32' },
    { id: 'totalSwitches', label: 'Total Switches', color: '#d32f2f' },
  ]), []);
  const toggleTopKey = (k) => setTopSelectedKeys((prev) => prev.includes(k) ? prev.filter(x => x !== k) : [...prev, k]);
  const selectAllTopKeys = () => setTopSelectedKeys(Array.isArray(topTimeline.keys) ? [...topTimeline.keys] : []);
  const clearAllTopKeys = () => setTopSelectedKeys([]);
  // KPI selection for the timeline (controls which series are shown)
  const KPI_DEFS = React.useMemo(() => ([
    { id: 'totalPhones', label: 'Total Phones', color: '#1976d2' },
    { id: 'phonesWithKEM', label: 'Phones with KEM', color: '#2e7d32' },
    { id: 'totalSwitches', label: 'Total Switches', color: '#d32f2f' },
    { id: 'totalLocations', label: 'Total Locations', color: '#f57c00' },
    { id: 'totalCities', label: 'Total Cities', color: '#6a1b9a' },
  ]), []);
  // For per-location timeline, exclude Locations/Cities which don't make sense in that context
  const KPI_DEFS_LOC = React.useMemo(() => KPI_DEFS.filter(k => k.id !== 'totalLocations' && k.id !== 'totalCities'), [KPI_DEFS]);
  // Default: exclude the very large 'Total Phones' so other KPIs are readable initially;
  // initialize from localStorage if available (including empty array)
  const [selectedKpis, setSelectedKpis] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const arr = saved.statistics?.selectedKpis;
      if (Array.isArray(arr)) return arr;
    } catch { /* ignore */ }
    return KPI_DEFS.filter(k => k.id !== 'totalPhones').map(k => k.id);
  });
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

  // Switch Port Cache für Statistics Switches
  const [switchPortCache, setSwitchPortCache] = React.useState({});

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
    // Rehydrate saved statistics preferences on first render
    try {
      const prefs = getStatisticsPrefs?.() || {};
      if (prefs.locSelected) setLocSelected(prefs.locSelected);
      if (typeof prefs.locInput === 'string') setLocInput(prefs.locInput);
      if (Array.isArray(prefs.selectedKpis)) setSelectedKpis(prefs.selectedKpis);
      if (Number.isFinite(prefs.topCount)) setTopCount(prefs.topCount);
      if (typeof prefs.topExtras === 'string') setTopExtras(prefs.topExtras);
      if (Number.isFinite(prefs.topDays)) setTopDays(prefs.topDays);
      if (typeof prefs.topKpi === 'string') setTopKpi(prefs.topKpi);
      if (Array.isArray(prefs.topSelectedKeys)) setTopSelectedKeys(prefs.topSelectedKeys);
      if (Number.isFinite(prefs.timelineDays)) setTimelineDays(prefs.timelineDays);
      statsHydratedRef.current = true;
    } catch { /* ignore */ }
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
  }, [getStatisticsPrefs]);

  // Persist key preferences when they change
  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ locSelected });
  }, [locSelected, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ locInput });
  }, [locInput, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ selectedKpis });
  }, [selectedKpis, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ topCount, topExtras, topDays, topKpi });
  }, [topCount, topExtras, topDays, topKpi, saveStatisticsPrefs]);

  // Funktion um Switch Port für einen Hostname zu holen
  const getSwitchPortForHostname = React.useCallback(async (hostname) => {
    if (!hostname) return null;

    // Prüfe Cache zuerst
    if (switchPortCache[hostname]) {
      return switchPortCache[hostname];
    }

    try {
      // Suche nach dem Hostname um Switch Port Daten zu bekommen
      const response = await fetch(`/api/search/?query=${encodeURIComponent(hostname)}&field=Switch Hostname&include_historical=false`);
      if (!response.ok) return null;

      const result = await response.json();
      if (result.success && result.data && result.data.length > 0) {
        // Finde den ersten Eintrag mit Switch Port Daten
        const entry = result.data.find(row => row && row["Switch Port"]);
        if (entry && entry["Switch Port"]) {
          const switchPort = entry["Switch Port"];
          // Cache das Ergebnis
          setSwitchPortCache(prev => ({
            ...prev,
            [hostname]: switchPort
          }));
          return switchPort;
        }
      }
    } catch (error) {
      console.warn('Failed to fetch switch port for hostname:', hostname, error);
    }

    // Cache auch negative Ergebnisse um wiederholte Anfragen zu vermeiden
    setSwitchPortCache(prev => ({
      ...prev,
      [hostname]: null
    }));

    return null;
  }, [switchPortCache]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    // Persist selected keys but throttle to avoid excessive writes
    const h = setTimeout(() => saveStatisticsPrefs?.({ topSelectedKeys }), 150);
    return () => clearTimeout(h);
  }, [topSelectedKeys, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ timelineDays });
  }, [timelineDays, saveStatisticsPrefs]);

  // Fetch Top-N locations aggregate timeline when controls change (debounced)
  React.useEffect(() => {
    const key = `${topCount}|${(topExtras || '').trim()}|${topDays}`;
    if (topLoadedKey === key && (topTimeline.dates || []).length) return;
    let abort = false;
    const controller = new AbortController();
    const h = setTimeout(async () => {
      try {
        setTopTimeline((t) => ({ ...t, loading: true, error: null }));
        const params = new URLSearchParams();
        params.set('count', String(topCount));
        params.set('limit', String(topDays || 0));
        if ((topExtras || '').trim()) params.set('extra', (topExtras || '').trim());
        params.set('mode', 'per_key');
        params.set('group', 'city');
        const r = await fetch(`/api/stats/timeline/top_locations?${params.toString()}`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          const dates = json.dates || [];
          const keys = json.keys || [];
          const seriesByKey = json.seriesByKey || {};
          const labels = json.labels || {};
          setTopTimeline({ loading: false, error: null, dates, keys, seriesByKey, labels, mode: 'per_key' });
          // Respect saved selection if available; otherwise select all
          try {
            const prefs = getStatisticsPrefs?.() || {};
            const savedSel = Array.isArray(prefs.topSelectedKeys) ? prefs.topSelectedKeys : [];
            const set = new Set(keys);
            const intersect = savedSel.filter(k => set.has(k));
            setTopSelectedKeys(intersect.length > 0 ? intersect : keys);
          } catch { setTopSelectedKeys(keys); }
          setTopLoadedKey(key);
        } else {
          setTopTimeline({ loading: false, error: json.message || 'No top-locations timeline available', dates: [], keys: [], seriesByKey: {}, mode: 'per_key' });
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setTopTimeline({ loading: false, error: 'Failed to load top-locations timeline', dates: [], keys: [], seriesByKey: {}, mode: 'per_key' });
      }
    }, 350);
    return () => { abort = true; controller.abort(); clearTimeout(h); };
  }, [topCount, topExtras, topDays, getStatisticsPrefs, topLoadedKey, topTimeline.dates]);

  // Build per-location line series for selected KPI
  const topSeriesPerKey = React.useMemo(() => {
    const dates = topTimeline.dates || [];
    const byKey = topTimeline.seriesByKey || {};
    const palette = ['#1976d2', '#2e7d32', '#0288d1', '#f57c00', '#6a1b9a', '#d32f2f', '#455a64', '#7b1fa2', '#00796b', '#c2185b'];
    const lastIdx = Math.max(0, dates.length - 1);
    const sortedKeys = [...(topSelectedKeys || [])].sort((a, b) => {
      const av = Number(byKey[a]?.[topKpi]?.[lastIdx] ?? 0);
      const bv = Number(byKey[b]?.[topKpi]?.[lastIdx] ?? 0);
      return bv - av; // desc
    });
    return sortedKeys.map((k, idx) => ({
      id: k,
      label: (topTimeline.labels && topTimeline.labels[k]) ? topTimeline.labels[k] : k,
      color: palette[idx % palette.length],
      data: (byKey[k]?.[topKpi] || new Array(dates.length).fill(0)),
    }));
  }, [topTimeline, topSelectedKeys, topKpi]);

  // Eagerly fetch global timeline on mount and when days changes
  React.useEffect(() => {
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setTimeline((t) => ({ ...t, loading: true, error: null }));
        const limit = Number.isFinite(timelineDays) ? Math.max(0, timelineDays) : 0;
        const r = await fetch(`/api/stats/timeline?limit=${limit}`, { signal: controller.signal });
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
          timelineLimitRef.current = limit;
        } else {
          setTimeline({ loading: false, error: json.message || 'No timeline available', series: [] });
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setTimeline({ loading: false, error: 'Failed to load timeline', series: [] });
      }
    })();
    return () => { abort = true; controller.abort(); };
  }, [timelineDays]);

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
    if (!locSelected) {
      // Reset stats when no location is selected
      setLocStats({
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
      setLocStatsLoading(false);
      setLocError(null);
      return;
    }
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

  // If timeline already loaded, refetch when days change
  React.useEffect(() => {
    const limit = Number.isFinite(timelineDays) ? Math.max(0, timelineDays) : 0;
    if (limit === timelineLimitRef.current) return;
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setTimeline((t) => ({ ...t, loading: true, error: null }));
        const r = await fetch(`/api/stats/timeline?limit=${limit}`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          setTimeline({ loading: false, error: null, series: json.series || [] });
          timelineLimitRef.current = limit;
        } else {
          setTimeline({ loading: false, error: json.message || 'No timeline available', series: [] });
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        setTimeline({ loading: false, error: 'Failed to load timeline', series: [] });
      }
    })();
    return () => { abort = true; controller.abort(); };
  }, [timelineDays]);

  // Fetch per-location timeline whenever the selected location changes
  React.useEffect(() => {
    if (!locSelected) {
      // Reset timeline when no location is selected
      setLocTimeline({ loading: false, error: null, series: [] });
      locTimelineLoadedKeyRef.current = '';
      return;
    }
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
          <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Justice institutions (Total Phones)" value={data.totalJustizPhones} loading={loading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Correctional Facility (Total Phones)" value={data.totalJVAPhones} loading={loading} /></Grid>
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
          <Grid container spacing={3} sx={{ alignItems: 'stretch' }}>
            {/* Justice institutions Category */}
            <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'primary.main' }}>
                Justice institutions (Justiz)
              </Typography>
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <List dense sx={{ flex: 1 }}>
                  {(data.phonesByModelJustiz || [])
                    .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                    .map(({ model, count }) => {
                      const label = String(model);
                      const lower = label.toLowerCase();
                      let color = 'default';
                      if (lower.includes('kem')) color = 'success';
                      else if (lower.includes('conference')) color = 'info';
                      else if (lower.includes('wireless')) color = 'warning';
                      else color = 'primary';
                      return (
                        <ListItem key={`justiz-${model}`} sx={{ py: 0.3, px: 0 }}>
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
                  {(data.phonesByModelJustiz || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length === 0 && !loading && (
                    <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>No data available</Typography>
                  )}
                </List>

                {/* Expandable detailed breakdown by location */}
                {!loading && (data.phonesByModelJustizDetails || []).length > 0 && (
                  <Accordion sx={{ mt: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="caption" color="text.secondary">
                        View by Location ({(data.phonesByModelJustizDetails || []).length} locations)
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: 0, minHeight: '400px' }}>
                      <List dense>
                        {(data.phonesByModelJustizDetails || []).map((location) => (
                          <ListItem key={`justiz-loc-${location.location}`} sx={{ py: 0.5, px: 0, flexDirection: 'column', alignItems: 'flex-start' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 0.5, alignItems: 'center' }}>
                              <Typography variant="body2" fontWeight={600} sx={{ color: 'primary.main' }}>
                                {location.location} - {location.city}
                              </Typography>
                              <Chip
                                label={`${location.totalPhones.toLocaleString()} phones`}
                                size="small"
                                variant="outlined"
                                color="primary"
                                sx={{ fontSize: '0.7rem', height: '20px' }}
                              />
                            </Box>
                            <Box sx={{ ml: 1, width: '100%' }}>
                              {location.models.slice(0, 3).map((modelData) => (
                                <Box key={`${location.location}-${modelData.model}`} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 0.1 }}>
                                  <Typography variant="caption" color="text.secondary">
                                    • {modelData.model}
                                  </Typography>
                                  <Typography variant="caption" fontWeight={500} sx={{ color: 'text.primary' }}>
                                    {modelData.count.toLocaleString()} {modelData.count === 1 ? 'phone' : 'phones'}
                                  </Typography>
                                </Box>
                              ))}
                              {location.models.length > 3 && (
                                <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', pl: 1 }}>
                                  +{location.models.length - 3} more models
                                </Typography>
                              )}
                            </Box>
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}
              </Box>
            </Grid>

            {/* Correctional Facility Category */}
            <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column' }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: 'warning.main' }}>
                Correctional Facility (JVA)
              </Typography>
              <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                <List dense sx={{ flex: 1 }}>
                  {(data.phonesByModelJVA || [])
                    .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                    .map(({ model, count }) => {
                      const label = String(model);
                      const lower = label.toLowerCase();
                      let color = 'default';
                      if (lower.includes('kem')) color = 'success';
                      else if (lower.includes('conference')) color = 'info';
                      else if (lower.includes('wireless')) color = 'error';
                      else color = 'warning';
                      return (
                        <ListItem key={`jva-${model}`} sx={{ py: 0.3, px: 0 }}>
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
                  {(data.phonesByModelJVA || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length === 0 && !loading && (
                    <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>No data available</Typography>
                  )}
                </List>

                {/* Expandable detailed breakdown by location */}
                {!loading && (data.phonesByModelJVADetails || []).length > 0 && (
                  <Accordion sx={{ mt: 1 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography variant="caption" color="text.secondary">
                        View by Location ({(data.phonesByModelJVADetails || []).length} locations)
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails sx={{ pt: 0, minHeight: '400px' }}>
                      <List dense>
                        {(data.phonesByModelJVADetails || []).map((location) => (
                          <ListItem key={`jva-loc-${location.location}`} sx={{ py: 0.5, px: 0, flexDirection: 'column', alignItems: 'flex-start' }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mb: 0.5, alignItems: 'center' }}>
                              <Typography variant="body2" fontWeight={600} sx={{ color: 'warning.main' }}>
                                {location.location} - {location.city}
                              </Typography>
                              <Chip
                                label={`${location.totalPhones.toLocaleString()} phones`}
                                size="small"
                                variant="outlined"
                                color="warning"
                                sx={{ fontSize: '0.7rem', height: '20px' }}
                              />
                            </Box>
                            <Box sx={{ ml: 1, width: '100%' }}>
                              {location.models.slice(0, 3).map((modelData) => (
                                <Box key={`${location.location}-${modelData.model}`} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 0.1 }}>
                                  <Typography variant="caption" color="text.secondary">
                                    • {modelData.model}
                                  </Typography>
                                  <Typography variant="caption" fontWeight={500} sx={{ color: 'text.primary' }}>
                                    {modelData.count.toLocaleString()} {modelData.count === 1 ? 'phone' : 'phones'}
                                  </Typography>
                                </Box>
                              ))}
                              {location.models.length > 3 && (
                                <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic', pl: 1 }}>
                                  +{location.models.length - 3} more models
                                </Typography>
                              )}
                            </Box>
                          </ListItem>
                        ))}
                      </List>
                    </AccordionDetails>
                  </Accordion>
                )}
              </Box>
            </Grid>
          </Grid>
        )}
      </Paper>

      {/* Statistics by Location */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.info.main}`, backgroundColor: (t) => alpha(t.palette.info.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'info.main' }}>Statistics by Location</Typography>

        {/* Two search fields side by side */}
        <Grid container spacing={2} sx={{ mb: 2 }}>
          {/* Location Code Search */}
          <Grid item xs={12} md={6}>
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
                  } else if (s === '') {
                    // Clear selection when field is empty
                    setLocSelected(null);
                  }
                } else {
                  setLocSelected(val);
                }
              }}
              inputValue={locInput}
              onInputChange={(_, val) => {
                setLocInput(val);
                // Clear selection if input is empty
                if (!val || val.trim() === '') {
                  setLocSelected(null);
                }
              }}
              filterOptions={(x) => x} // server-side filtering
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Search by Location Code"
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
          </Grid>

          {/* City Name Search */}
          <Grid item xs={12} md={6}>
            <Autocomplete
              options={Object.values(cityNameByCode3).sort()}
              freeSolo
              // Keep popup size fixed and make options scrollable
              slotProps={{
                paper: { sx: { maxHeight: 320, overflowY: 'auto' } },
                listbox: { sx: { maxHeight: 280, overflowY: 'auto' } },
              }}
              ListboxProps={{
                style: { maxHeight: 280, overflowY: 'auto' },
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Search by City Name"
                  placeholder="Type city name (e.g., München, Augsburg)"
                  size="small"
                />
              )}
              onChange={(_, value) => {
                if (value) {
                  // Find location code for this city name
                  const cityCode = Object.entries(cityNameByCode3).find(([code, name]) =>
                    name.toLowerCase() === value.toLowerCase()
                  )?.[0];

                  if (cityCode) {
                    setLocSelected(cityCode);
                    setLocInput(cityCode);
                  }
                }
              }}
              filterOptions={(options, { inputValue }) => {
                // If no input, show all cities (but limited by maxHeight)
                if (!inputValue.trim()) {
                  return options;
                }
                // Otherwise filter by input
                const filtered = options.filter(option =>
                  option.toLowerCase().includes(inputValue.toLowerCase())
                );
                return filtered;
              }}
              getOptionLabel={(option) => option}
              renderOption={(props, option) => {
                // Find the corresponding location code
                const cityCode = Object.entries(cityNameByCode3).find(([code, name]) =>
                  name === option
                )?.[0];

                return (
                  <li {...props}>
                    <Box>
                      <Typography variant="body2">{option}</Typography>
                      {cityCode && (
                        <Typography variant="caption" color="text.secondary">
                          Code: {cityCode}
                        </Typography>
                      )}
                    </Box>
                  </li>
                );
              }}
            />
          </Grid>
        </Grid>

        {locError && (
          <Box sx={{ mb: 2 }}>
            <Alert severity="info" variant="outlined">{locError}</Alert>
          </Box>
        )}

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
                <Box>
                  {/* Justice institutions (Justiz) */}
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'primary.main', mb: 0.5 }}>
                    Justice institutions (Justiz)
                  </Typography>
                  <List dense sx={{ mb: 1 }}>
                    {(locStats.phonesByModelJustiz || [])
                      .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                      .slice(0, 5)
                      .map(({ model, count }) => (
                        <ListItem key={`justiz-${model}`} sx={{ py: 0.2, px: 0 }}>
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
                    {(locStats.phonesByModelJustiz || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length === 0 && !locStatsLoading && (
                      <Typography variant="body2" color="text.secondary" sx={{ px: 0, py: 0.5 }}>No data</Typography>
                    )}
                  </List>

                  {/* Correctional Facility (JVA) */}
                  <Typography variant="body2" sx={{ fontWeight: 600, color: 'warning.main', mb: 0.5 }}>
                    Correctional Facility (JVA)
                  </Typography>
                  <List dense>
                    {(locStats.phonesByModelJVA || [])
                      .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                      .slice(0, 5)
                      .map(({ model, count }) => (
                        <ListItem key={`jva-${model}`} sx={{ py: 0.2, px: 0 }}>
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
                    {(locStats.phonesByModelJVA || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length === 0 && !locStatsLoading && (
                      <Typography variant="body2" color="text.secondary" sx={{ px: 0, py: 0.5 }}>No data</Typography>
                    )}
                  </List>
                </Box>
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
                            {/* Switch Hostname mit getrennten Klick-Bereichen wie in DataTable */}
                            {(() => {
                              const hostname = sw.hostname;
                              // Split hostname in hostname Teil (vor erstem .) und Domain Teil
                              const parts = hostname.split('.');
                              const hostnameShort = parts[0] || hostname;
                              const domainPart = parts.length > 1 ? '.' + parts.slice(1).join('.') : '';

                              const copyHostnameTitle = `Copy hostname: ${hostnameShort}`;

                              const sshTitle = sshUsername
                                ? `Connect SSH ${sshUsername}@${hostname}`
                                : `SSH connection (SSH username not set)`;

                              return (
                                <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center' }}>
                                  {/* Hostname short part - kopiert hostname Teil vor dem . */}
                                  <Tooltip arrow placement="top" title={copyHostnameTitle}>
                                    <Typography
                                      variant="body2"
                                      component="span"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        // Copy hostname short part (before first .)
                                        copyToClipboard(hostnameShort).then(success => {
                                          if (success) {
                                            showCopyToast('Copied hostname', hostnameShort);
                                          } else {
                                            toast.error(`❌ Copy failed`, {
                                              autoClose: 2000,
                                              pauseOnHover: true,
                                              pauseOnFocusLoss: false
                                            });
                                          }
                                        });
                                      }}
                                      sx={{
                                        color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.8)' : '#4caf50',
                                        cursor: 'pointer',
                                        textDecoration: 'underline',
                                        '&:hover': {
                                          color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 1)' : '#388e3c',
                                          textDecoration: 'underline'
                                        }
                                      }}
                                    >
                                      {hostnameShort}
                                    </Typography>
                                  </Tooltip>

                                  {/* Domain part - SSH Verbindung + kopiert Switch Port Cisco Format */}
                                  {domainPart && (
                                    <Tooltip arrow placement="top" title={sshTitle}>
                                      <Typography
                                        variant="body2"
                                        component="span"
                                        onClick={async (e) => {
                                          e.stopPropagation();

                                          // First: Try to get switch port data and copy Cisco format
                                          try {
                                            const switchPort = await getSwitchPortForHostname(hostname);
                                            if (switchPort) {
                                              const ciscoFormat = convertToCiscoFormat(switchPort);
                                              if (ciscoFormat && ciscoFormat.trim() !== '') {
                                                await copyToClipboard(ciscoFormat);
                                                showCopyToast('Copied Cisco port', ciscoFormat);
                                              } else {
                                                showCopyToast('Copied switch port', switchPort);
                                                await copyToClipboard(switchPort);
                                              }
                                            }
                                          } catch (error) {
                                            console.warn('Failed to copy switch port:', error);
                                          }

                                          // Second: SSH link functionality
                                          if (sshUsername && sshUsername.trim() !== '') {
                                            const sshUrl = `ssh://${sshUsername}@${hostname}`;
                                            toast.success(`🔗 SSH: ${sshUsername}@${hostname}`, { autoClose: 1000, pauseOnHover: false });
                                            setTimeout(() => { window.location.href = sshUrl; }, 150);
                                          } else {
                                            // If no SSH username, show warning
                                            const ToastContent = () => (
                                              <div>
                                                ⚠️ SSH username not configured!{' '}
                                                <span
                                                  onClick={() => {
                                                    try { navigateToSettings?.(); } catch { }
                                                    try { toast.dismiss(); } catch { }
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
                                            toast.warning(<ToastContent />, {
                                              autoClose: 6000,
                                              pauseOnHover: true,
                                              pauseOnFocusLoss: false
                                            });
                                          }
                                        }}
                                        sx={{
                                          color: theme => theme.palette.mode === 'dark' ? 'rgba(139, 195, 74, 0.8)' : '#689f38',
                                          cursor: 'pointer',
                                          textDecoration: 'underline',
                                          '&:hover': {
                                            color: theme => theme.palette.mode === 'dark' ? 'rgba(139, 195, 74, 1)' : '#558b2f',
                                            textDecoration: 'underline'
                                          }
                                        }}
                                      >
                                        {domainPart}
                                      </Typography>
                                    </Tooltip>
                                  )}
                                </Box>
                              );
                            })()}
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
                                  <Typography
                                    variant="body2"
                                    component="a"
                                    href={`http://${encodeURIComponent(ip)}`}
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
                                    {ip}
                                  </Typography>
                                </Tooltip>
                              ) : 'n/a'}
                            </TableCell>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                              {mac ? (
                                <Typography
                                  variant="body2"
                                  component="a"
                                  href={`/?q=${encodeURIComponent(mac)}`}
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
                                  {mac}
                                </Typography>
                              ) : 'n/a'}
                            </TableCell>
                            <TableCell sx={{ whiteSpace: 'nowrap' }}>
                              {p['Switch Hostname'] ? (() => {
                                const hostname = p['Switch Hostname'];
                                // Split hostname in hostname Teil (vor erstem .) und Domain Teil
                                const parts = hostname.split('.');
                                const hostnameShort = parts[0] || hostname;
                                const domainPart = parts.length > 1 ? '.' + parts.slice(1).join('.') : '';

                                const copyHostnameTitle = `Copy hostname: ${hostnameShort}`;
                                const sshTitle = sshUsername
                                  ? `Connect SSH ${sshUsername}@${hostname}`
                                  : `SSH connection (SSH username not set)`;

                                return (
                                  <Box component="span" sx={{ display: 'inline-flex', alignItems: 'center' }}>
                                    {/* Hostname short part - kopiert hostname Teil vor dem . */}
                                    <Tooltip arrow placement="top" title={copyHostnameTitle}>
                                      <Typography
                                        variant="body2"
                                        component="span"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          // Copy hostname short part (before first .)
                                          copyToClipboard(hostnameShort).then(success => {
                                            if (success) {
                                              showCopyToast('Copied hostname', hostnameShort);
                                            } else {
                                              toast.error(`❌ Copy failed`, {
                                                autoClose: 2000,
                                                pauseOnHover: true,
                                                pauseOnFocusLoss: false
                                              });
                                            }
                                          });
                                        }}
                                        sx={{
                                          color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.8)' : '#4caf50',
                                          cursor: 'pointer',
                                          textDecoration: 'underline',
                                          '&:hover': {
                                            color: theme => theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 1)' : '#388e3c',
                                            textDecoration: 'underline'
                                          }
                                        }}
                                      >
                                        {hostnameShort}
                                      </Typography>
                                    </Tooltip>

                                    {/* Domain part - SSH Verbindung */}
                                    {domainPart && (
                                      <Tooltip arrow placement="top" title={sshTitle}>
                                        <Typography
                                          variant="body2"
                                          component="span"
                                          onClick={async (e) => {
                                            e.stopPropagation();

                                            // First: Copy Cisco port format
                                            const ciscoFormat = p["Switch Port"] ? convertToCiscoFormat(p["Switch Port"]) : '';
                                            if (ciscoFormat && ciscoFormat.trim() !== '') {
                                              const copied = await copyToClipboard(ciscoFormat);
                                              if (copied) {
                                                showCopyToast('Copied Cisco port', ciscoFormat);
                                              } else {
                                                toast.error(`❌ Copy failed`, {
                                                  autoClose: 2000,
                                                  pauseOnHover: true,
                                                  pauseOnFocusLoss: false
                                                });
                                              }
                                            } else {
                                              toast.warning('No switch port available to copy', {
                                                autoClose: 2000,
                                                pauseOnHover: true
                                              });
                                            }

                                            // Second: SSH link functionality
                                            if (sshUsername && sshUsername.trim() !== '') {
                                              const sshUrl = `ssh://${sshUsername}@${hostname}`;
                                              toast.success(`🔗 SSH: ${sshUsername}@${hostname}`, { autoClose: 1000, pauseOnHover: false });
                                              setTimeout(() => { window.location.href = sshUrl; }, 150);
                                            } else {
                                              // If no SSH username, show warning but don't copy hostname again
                                              const ToastContent = () => (
                                                <div>
                                                  📋 Copied Cisco port! ⚠️ SSH username not configured!{' '}
                                                  <span
                                                    onClick={() => {
                                                      navigateToSettings();
                                                      toast.dismiss();
                                                    }}
                                                    style={{
                                                      color: '#4f46e5',
                                                      textDecoration: 'underline',
                                                      cursor: 'pointer',
                                                      fontWeight: 'bold'
                                                    }}
                                                  >
                                                    Go to Settings
                                                  </span>{' '}to set your SSH username.
                                                </div>
                                              );
                                              toast.error(<ToastContent />, { autoClose: false, closeOnClick: false, hideProgressBar: true, closeButton: true, pauseOnHover: true });
                                            }
                                          }}
                                          sx={{
                                            color: theme => theme.palette.mode === 'dark' ? 'rgba(100, 149, 237, 0.8)' : '#1976d2',
                                            cursor: 'pointer',
                                            textDecoration: 'underline',
                                            '&:hover': {
                                              color: theme => theme.palette.mode === 'dark' ? 'rgba(100, 149, 237, 1)' : '#1565c0',
                                              textDecoration: 'underline'
                                            }
                                          }}
                                        >
                                          {domainPart}
                                        </Typography>
                                      </Tooltip>
                                    )}
                                  </Box>
                                );
                              })() : 'n/a'}
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
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1, flexWrap: 'wrap' }}>
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>Timeline ({(timeline.series || []).length} days)</Typography>
          <TextField
            size="small"
            type="number"
            label="Days (0 = full)"
            value={timelineDays}
            onChange={(e) => {
              const v = parseInt(e.target.value || '0', 10);
              setTimelineDays(Number.isFinite(v) ? Math.max(0, v) : 0);
            }}
            sx={{ width: 160, ml: 'auto' }}
          />
        </Box>
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

      {/* Top Cities Timeline */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.primary.main}`, backgroundColor: (t) => alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.06 : 0.04) }}>
        <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>Top Cities Timeline — {TOP_KPI_DEFS.find(d => d.id === topKpi)?.label || ''} ({(topTimeline.dates || []).length} days)</Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1, alignItems: 'center' }}>
          <Typography variant="body2" color="text.secondary">Show:</Typography>
          {[
            { n: 10, label: 'Top 10' },
          ].map(({ n, label }) => (
            <Chip
              key={n}
              label={label}
              size="small"
              color={topCount === n ? 'success' : 'default'}
              variant={topCount === n ? 'filled' : 'outlined'}
              onClick={() => { setTopCount(n); setTopLoadedKey(''); }}
            />
          ))}
          <Typography variant="body2" color="text.secondary" sx={{ ml: 1 }}>KPI:</Typography>
          {TOP_KPI_DEFS.map((k) => (
            <Chip
              key={k.id}
              label={k.label}
              size="small"
              color={topKpi === k.id ? 'success' : 'default'}
              variant={topKpi === k.id ? 'filled' : 'outlined'}
              onClick={() => setTopKpi(k.id)}
            />
          ))}
          <TextField
            size="small"
            type="number"
            label="Days (0 = full)"
            value={topDays}
            onChange={(e) => { const v = parseInt(e.target.value || '0', 10); setTopDays(Number.isFinite(v) ? Math.max(0, v) : 0); setTopLoadedKey(''); }}
            sx={{ width: 140 }}
          />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, ml: 'auto', minWidth: 300 }}>
            <TextField
              size="small"
              fullWidth
              label="Add city codes (3 letters, comma-separated)"
              placeholder="e.g., ABC, XYZ"
              value={topExtras}
              onChange={(e) => { setTopExtras(e.target.value); setTopLoadedKey(''); }}
            />
          </Box>
        </Box>
        {/* Select/deselect locations */}
        {(topTimeline.keys || []).length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1 }}>
            <Chip size="small" label="Select all" variant="outlined" onClick={selectAllTopKeys} />
            <Chip size="small" label="Clear all" variant="outlined" onClick={clearAllTopKeys} />
            {(topTimeline.keys || []).map((k) => (
              <Chip
                key={k}
                size="small"
                label={(topTimeline.labels && topTimeline.labels[k]) ? topTimeline.labels[k] : k}
                color={topSelectedKeys.includes(k) ? 'success' : 'default'}
                variant={topSelectedKeys.includes(k) ? 'filled' : 'outlined'}
                onClick={() => toggleTopKey(k)}
              />
            ))}
          </Box>
        )}
        {/* KPIs fixed for this timeline: Total Phones, Phones with KEM, Total Switches (aggregated over selected keys) */}
        {topTimeline.loading ? (
          <Skeleton variant="rectangular" height={220} />
        ) : topTimeline.error ? (
          <Alert severity="info" variant="outlined">{topTimeline.error}</Alert>
        ) : (
          <Box sx={{ width: '100%', overflowX: 'auto' }}>
            <LineChart
              height={380}
              xAxis={[{ data: (topTimeline.dates || []).map((d) => String(d).slice(5)), scaleType: 'point' }]}
              series={topSeriesPerKey}
              margin={{ left: 40, right: 20, top: 16, bottom: 24 }}
              slotProps={{
                legend: { hidden: true },
                tooltip: {
                  sx: {
                    maxWidth: 640,
                    '& ul': {
                      columns: topCount >= 50 ? 4 : topCount >= 25 ? 2 : 1,
                      columnGap: 16,
                      margin: 0,
                      padding: 0,
                    },
                  },
                },
              }}
              sx={{ minWidth: 520 }}
            />
            {(topSelectedKeys || []).length > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                Showing {topSelectedKeys.length} location lines
              </Typography>
            )}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
