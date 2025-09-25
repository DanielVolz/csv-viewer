import React from 'react';
import { Box, Card, CardContent, Grid, Typography, List, ListItem, ListItemText, ListItemButton, ListItemIcon, Paper, Skeleton, Alert, Autocomplete, TextField, Chip, Accordion, AccordionSummary, AccordionDetails, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Button, Snackbar, Divider, InputAdornment, CircularProgress, IconButton } from '@mui/material';
import { Link, Routes, Route, useLocation, useNavigate } from 'react-router-dom';
import { LineChart } from '@mui/x-charts';
import { alpha } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CloseIcon from '@mui/icons-material/Close';
import SearchIcon from '@mui/icons-material/Search';
import PhoneIcon from '@mui/icons-material/Phone';
import RouterIcon from '@mui/icons-material/Router';
import LocationOnIcon from '@mui/icons-material/LocationOn';
import LocationCityIcon from '@mui/icons-material/LocationCity';
import ExtensionIcon from '@mui/icons-material/Extension';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import GavelIcon from '@mui/icons-material/Gavel';
import SecurityIcon from '@mui/icons-material/Security';
import PublicIcon from '@mui/icons-material/Public';
import PlaceIcon from '@mui/icons-material/Place';
import BusinessIcon from '@mui/icons-material/Business';
import DoneAllIcon from '@mui/icons-material/DoneAll';
import ClearAllIcon from '@mui/icons-material/ClearAll';
import TerminalIcon from '@mui/icons-material/Terminal';
import { toast } from 'react-toastify';
import { useSettings } from '../contexts/SettingsContext';

// --- Local helpers (restored to satisfy lint and preserve behavior) ---
// Pick an icon for KPI cards based on title
function getKPIIcon(title) {
  const t = String(title || '').toLowerCase();
  if (t.includes('phone') && t.includes('kem')) return ExtensionIcon;
  if (t.includes('phone')) return PhoneIcon;
  if (t.includes('switch')) return RouterIcon;
  if (t.includes('location') || t.includes('city')) return LocationCityIcon;
  if (t.includes('timeline') || t.includes('trend')) return TrendingUpIcon;
  return PublicIcon;
}

// Heuristic: detect MAC address strings in common formats and exclude from model lists
function isMacLike(value) {
  if (!value) return false;
  const s = String(value).trim();
  const sep6 = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$/; // AA:BB:CC:DD:EE:FF or AA-BB-CC-DD-EE-FF
  const dotted = /^([0-9A-Fa-f]{4}\.){2}([0-9A-Fa-f]{4})$/; // AABB.CCDD.EEFF
  const plain12 = /^[0-9A-Fa-f]{12}$/; // AABBCCDDEEFF
  return sep6.test(s) || dotted.test(s) || plain12.test(s);
}

// Determine if a location code belongs to JVA (correctional facility)
function isJVALocation(locationCode) {
  if (!locationCode) return false;
  const code = String(locationCode).trim();
  // JVA codes end with 50 or 51 (e.g., SRX50, SRX51)
  return /50$|51$/.test(code);
}

// Justice locations are those not matching the JVA pattern
function isJusticeLocation(locationCode) {
  if (!locationCode) return false;
  return !isJVALocation(locationCode);
}

// Group locations by city code for details accordions
function groupLocationsByCity(detailsArray) {
  const arr = Array.isArray(detailsArray) ? detailsArray : [];
  const byCity = new Map();
  for (const item of arr) {
    const loc = String(item.location || '').toUpperCase();
    const cityCode = loc.slice(0, 3);
    const cityName = item.cityName || item.city || '';
    const entry = byCity.get(cityCode) || { cityCode, cityName, totalCityPhones: 0, locations: [] };
    const total = Number(item.totalPhones || item.count || 0);
    entry.totalCityPhones += Number.isFinite(total) ? total : 0;
    entry.locations.push({
      location: loc,
      totalPhones: total,
      models: Array.isArray(item.models) ? item.models : [],
    });
    byCity.set(cityCode, entry);
  }
  return Array.from(byCity.values()).sort((a, b) => String(a.cityCode).localeCompare(String(b.cityCode)));
}
// Enhanced StatCard with React.memo, icons, and animations
const StatCard = React.memo(function StatCard({ title, value, loading, tone = 'primary' }) {
  const IconComponent = getKPIIcon(title);

  return (
    <Card
      elevation={0}
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 3,
        background: (theme) =>
          `linear-gradient(135deg, ${alpha(theme.palette[tone].main, theme.palette.mode === 'dark' ? 0.15 : 0.08)} 0%, ${alpha(theme.palette[tone].main, theme.palette.mode === 'dark' ? 0.08 : 0.04)} 100%)`,
        borderLeft: '4px solid',
        borderLeftColor: (theme) => theme.palette[tone].main,
        position: 'relative',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          top: 0,
          right: 0,
          width: '100px',
          height: '100px',
          background: (theme) =>
            `radial-gradient(circle at center, ${alpha(theme.palette[tone].main, 0.1)} 0%, transparent 70%)`,
          borderRadius: '50%',
          transform: 'translate(30px, -30px)',
        }
      }}
    >
      <CardContent sx={{ position: 'relative', zIndex: 1 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
          <Typography
            variant="overline"
            sx={{
              color: (theme) => theme.palette[tone].main,
              fontWeight: 600,
              letterSpacing: '0.1em'
            }}
          >
            {title}
          </Typography>
          <IconComponent
            sx={{
              color: (theme) => alpha(theme.palette[tone].main, 0.7),
              fontSize: '1.5rem',
            }}
          />
        </Box>
        {loading ? (
          <Skeleton
            variant="text"
            sx={{
              fontSize: '2.5rem',
              width: 140,
              borderRadius: 1
            }}
          />
        ) : (
          <Typography
            variant="h4"
            sx={{
              fontWeight: 700,
              background: (theme) =>
                `linear-gradient(45deg, ${theme.palette.text.primary} 30%, ${theme.palette[tone].main} 90%)`,
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              transition: 'all 0.3s ease',
            }}
          >
            {value?.toLocaleString?.() ?? value}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
});

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

const StatisticsPage = React.memo(function StatisticsPage() {
  const locationRouter = useLocation();
  const navigate = useNavigate();
  const { sshUsername, navigateToSettings, getStatisticsPrefs, saveStatisticsPrefs } = useSettings?.() || {};

  // Color themes for Justice vs JVA differentiation
  const justiceTheme = {
    primary: '#1976d2',      // Blue - primary
    light: '#bbdefb',        // Light blue
    background: 'rgba(25, 118, 210, 0.08)',  // Light blue background
    border: 'rgba(25, 118, 210, 0.2)',       // Blue border
    accent: '#0d47a1'        // Dark blue accent
  };

  const jvaTheme = {
    primary: '#f57c00',      // Orange - warning
    light: '#ffe0b2',        // Light orange
    background: 'rgba(245, 124, 0, 0.08)',   // Light orange background
    border: 'rgba(245, 124, 0, 0.2)',        // Orange border
    accent: '#e65100'        // Dark orange accent
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

  // Separate state for city information (loaded independently)
  const [cityNameByCode3, setCityNameByCode3] = React.useState({});

  // Load city information independently
  React.useEffect(() => {
    let abort = false;
    const controller = new AbortController();

    (async () => {
      try {
        const r = await fetch('/api/stats/fast/cities', { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;

        if (json.success && json.cityMap) {
          setCityNameByCode3(json.cityMap);
        }
      } catch (e) {
        if (e.name === 'AbortError') return;
        console.warn('Failed to load city data:', e);
      }
    })();

    return () => { abort = true; controller.abort(); };
  }, []);

  const [fileMeta, setFileMeta] = React.useState(null);
  const statsHydratedRef = React.useRef(false);
  // Timeline state (configurable days)
  const [timeline, setTimeline] = React.useState({ loading: false, error: null, series: [] });
  const [backfillInfo, setBackfillInfo] = React.useState(null);
  const [timelineDays, setTimelineDays] = React.useState(0); // 0 = all days by default
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

  // Accordion expansion functions for View by Location
  const expandAllJustizCities = () => {
    const allCities = groupLocationsByCity(data.phonesByModelJustizDetails || []);
    const expanded = {};
    allCities.forEach(cityGroup => {
      expanded[`justiz-city-${cityGroup.cityCode}`] = true;
    });
    setJustizCitiesExpanded(expanded);
  };

  const collapseAllJustizCities = () => setJustizCitiesExpanded({});

  const expandAllJvaCities = () => {
    const allCities = groupLocationsByCity(data.phonesByModelJVADetails || []);
    const expanded = {};
    allCities.forEach(cityGroup => {
      expanded[`jva-city-${cityGroup.cityCode}`] = true;
    });
    setJvaCitiesExpanded(expanded);
  };

  const collapseAllJvaCities = () => setJvaCitiesExpanded({});

  // Fast accordion transitions
  const fastTransitionProps = {
    timeout: 150,
    style: { transitionDuration: '150ms' }
  };
  // KPI selection for the timelines (independent per scope)
  const KPI_DEFS = React.useMemo(() => ([
    { id: 'totalPhones', label: 'Total Phones', color: '#1976d2' },
    { id: 'phonesWithKEM', label: 'Phones with KEM', color: '#2e7d32' },
    { id: 'totalSwitches', label: 'Total Switches', color: '#d32f2f' },
    { id: 'totalLocations', label: 'Total Locations', color: '#f57c00' },
    { id: 'totalCities', label: 'Total Cities', color: '#6a1b9a' },
  ]), []);
  // For per-location timeline, exclude Locations/Cities which don't make sense in that context
  const KPI_DEFS_LOC = React.useMemo(() => KPI_DEFS.filter(k => k.id !== 'totalLocations' && k.id !== 'totalCities'), [KPI_DEFS]);
  // Defaults: exclude 'Total Phones' so other KPIs are readable initially
  const defaultKpisGlobal = React.useMemo(() => KPI_DEFS.filter(k => k.id !== 'totalPhones').map(k => k.id), [KPI_DEFS]);
  const defaultKpisLoc = React.useMemo(() => KPI_DEFS_LOC.filter(k => k.id !== 'totalPhones').map(k => k.id), [KPI_DEFS_LOC]);
  // Global timeline KPI selection
  const [selectedKpisGlobal, setSelectedKpisGlobal] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const stats = saved.statistics || {};
      if (Array.isArray(stats.selectedKpisGlobal)) return stats.selectedKpisGlobal;
      if (Array.isArray(stats.selectedKpis)) return stats.selectedKpis; // backward compat
    } catch { /* ignore */ }
    return defaultKpisGlobal;
  });
  const toggleKpiGlobal = (id) => {
    setSelectedKpisGlobal((prev) => prev.includes(id) ? prev.filter(k => k !== id) : [...prev, id]);
  };

  const selectAllGlobalKpis = () => setSelectedKpisGlobal(KPI_DEFS.map(k => k.id));
  const clearAllGlobalKpis = () => setSelectedKpisGlobal([]);
  // Per-location timeline KPI selection (independent)
  const [selectedKpisLoc, setSelectedKpisLoc] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      const stats = saved.statistics || {};
      if (Array.isArray(stats.selectedKpisLoc)) return stats.selectedKpisLoc;
      if (Array.isArray(stats.selectedKpis)) return stats.selectedKpis; // fallback
    } catch { /* ignore */ }
    return defaultKpisLoc;
  });
  const toggleKpiLoc = (id) => {
    setSelectedKpisLoc((prev) => prev.includes(id) ? prev.filter(k => k !== id) : [...prev, id]);
  };

  const selectAllLocKpis = () => setSelectedKpisLoc(KPI_DEFS_LOC.map(k => k.id));
  const clearAllLocKpis = () => setSelectedKpisLoc([]);

  // Location-specific state
  const [locInput, setLocInput] = React.useState('');
  const [locError, setLocError] = React.useState(null);

  // Location search dropdown state
  const [locationSuggestions, setLocationSuggestions] = React.useState([]);
  const [showLocationDropdown, setShowLocationDropdown] = React.useState(false);
  const [selectedSuggestionIndex, setSelectedSuggestionIndex] = React.useState(-1);
  const [isSearchingLocations, setIsSearchingLocations] = React.useState(false);
  // Performance: cache suggestions and abort in-flight requests
  const suggestionsCacheRef = React.useRef(new Map()); // key: query, value: array
  const suggestionsControllerRef = React.useRef(null);
  const suggestRequestSeqRef = React.useRef(0);

  // Accordion expansion state for View by Location sections
  const [justizCitiesExpanded, setJustizCitiesExpanded] = React.useState({});
  const [jvaCitiesExpanded, setJvaCitiesExpanded] = React.useState({});

  const [locSelected, setLocSelected] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      return saved.statistics?.lastSelectedLocation || null;
    } catch {
      return null;
    }
  });
  const [debouncedLocSelected, setDebouncedLocSelected] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      return saved.statistics?.lastSelectedLocation || null;
    } catch {
      return null;
    }
  }); // Debounced version for API calls
  const [snackbar, setSnackbar] = React.useState({ open: false, message: '' });
  const [isUiPending, startTransition] = React.useTransition();
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

  const locationActionLoading = isSearchingLocations || locStatsLoading;

  // Switch Port Cache für Statistics Switches
  const [switchPortCache, setSwitchPortCache] = React.useState({});

  // Location-specific timeline state
  const [locTimeline, setLocTimeline] = React.useState({ loading: false, error: null, series: [] });
  const locTimelineLoadedKeyRef = React.useRef('');
  // Collapsible state for per-location timeline (default collapsed)
  const [locTimelineExpanded, setLocTimelineExpanded] = React.useState(false);

  // Local input state for immediate UI response, debounced for filtering
  const [localInput, setLocalInput] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      return saved.statistics?.lastSelectedLocation || '';
    } catch {
      return '';
    }
  });
  const [citySearchInput, setCitySearchInput] = React.useState('');
  const [cityAutocompleteOpen, setCityAutocompleteOpen] = React.useState(false);
  // Uncontrolled input ref to keep typing instant
  const locInputRef = React.useRef(null);

  // Location search with dropdown functionality
  const searchLocationSuggestions = React.useCallback(async (query) => {
    const q = (query || '').trim();
    if (!q) {
      startTransition(() => setLocationSuggestions([]));
      startTransition(() => setShowLocationDropdown(false));
      return;
    }
    // Now allow 1+ characters; backend handles broad prefixes efficiently

    // Helper: prepend city prefix option (e.g., Mxx München) as the first item when user typed exactly 3 letters
    const withCityPrefixOption = (qStr, arr) => {
      const out = Array.isArray(arr) ? [...arr] : [];
      const three = qStr.length === 3 && /^[a-zA-Z]{3}$/.test(qStr);
      if (three) {
        const code3Upper = qStr.substring(0, 3).toUpperCase();
        const code3Mxx = code3Upper.replace(/X/g, 'x');
        const code3MXX = code3Upper;
        // Try to resolve city name from preloaded map; if missing, we still inject the prefix item (city can be resolved at render time)
        let cityName = cityNameByCode3?.[code3Mxx] || cityNameByCode3?.[code3MXX];
        if (!cityName && Array.isArray(arr) && arr.length) {
          const hit = arr.find(s => String(s.code || '').toUpperCase().startsWith(code3Upper) && s.city);
          if (hit && hit.city) cityName = hit.city;
        }
        // Avoid duplicate if already present
        const exists = out.some(s => String(s.code || '').toUpperCase().replace(/X/g, 'x') === code3Mxx);
        const prefixItem = { code: code3Mxx, city: cityName, isPrefixAll: true };
        if (!exists) {
          out.unshift(prefixItem);
        } else {
          // Ensure the prefix item is first
          const filtered = out.filter(s => String(s.code || '').toUpperCase().replace(/X/g, 'x') !== code3Mxx);
          out.length = 0; out.push(prefixItem, ...filtered);
        }
      }
      return out;
    };

    // Serve from cache if available
    if (suggestionsCacheRef.current.has(q)) {
      const cached = suggestionsCacheRef.current.get(q) || [];
      const merged = withCityPrefixOption(q, cached);
      startTransition(() => setLocationSuggestions(merged));
      startTransition(() => setShowLocationDropdown(merged.length > 0));
      startTransition(() => setSelectedSuggestionIndex(-1));
      return;
    }

    try {
      // Abort previous request
      if (suggestionsControllerRef.current) {
        try { suggestionsControllerRef.current.abort(); } catch { /* ignore */ }
      }
      const controller = new AbortController();
      suggestionsControllerRef.current = controller;
      setIsSearchingLocations(true);

      // Adaptive limit: fewer items for very short prefixes
      const limit = q.length === 2 ? 30 : (q.length === 3 ? 60 : 80);
      const seq = ++suggestRequestSeqRef.current;
      const response = await fetch(`/api/stats/fast/locations/suggest?q=${encodeURIComponent(q)}&limit=${limit}`,
        { signal: controller.signal });
      const data = await response.json();

      // Ignore out-of-order responses
      if (seq !== suggestRequestSeqRef.current) return;

      if (data.success && Array.isArray(data.suggestions)) {
        // Cache result (simple LRU cap)
        suggestionsCacheRef.current.set(q, data.suggestions);
        if (suggestionsCacheRef.current.size > 200) {
          const firstKey = suggestionsCacheRef.current.keys().next().value;
          suggestionsCacheRef.current.delete(firstKey);
        }
        const merged = withCityPrefixOption(q, data.suggestions);
        startTransition(() => setLocationSuggestions(merged));
        startTransition(() => setShowLocationDropdown(merged.length > 0));
        startTransition(() => setSelectedSuggestionIndex(-1));
      } else {
        startTransition(() => setLocationSuggestions([]));
        startTransition(() => setShowLocationDropdown(false));
      }
    } catch (error) {
      console.error('Error fetching location suggestions:', error);
      startTransition(() => setLocationSuggestions([]));
      startTransition(() => setShowLocationDropdown(false));
    } finally {
      setIsSearchingLocations(false);
    }
  }, [cityNameByCode3]);

  // Timeout ref for debouncing suggestions only
  const timeoutRef = React.useRef();             // suggestions debounce

  const debouncedLocationSearch = React.useCallback((query) => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      searchLocationSuggestions(query);
    }, 180);
  }, [searchLocationSuggestions]);

  const clearLocationSelection = React.useCallback(() => {
    setLocSelected(null);
    setLocInput('');
    setLocalInput('');
    setLocStats({
      totalPhones: 0,
      totalSwitches: 0,
      phonesWithKEM: 0,
      phonesByModel: [],
      phonesByModelJustiz: [],
      phonesByModelJVA: [],
      vlanUsage: [],
      switches: [],
      kemPhones: [],
    });
    setLocStatsLoading(false);
    setLocError(null);
    setLocationSuggestions([]);
    setShowLocationDropdown(false);
    setSelectedSuggestionIndex(-1);
    if (locInputRef.current) {
      try { locInputRef.current.value = ''; } catch { /* ignore */ }
    }
    saveStatisticsPrefs?.({ lastSelectedLocation: null });
  }, [saveStatisticsPrefs]);

  const handleLocationInputChange = React.useCallback((e) => {
    const val = e.target.value || '';
    setLocInput(val);

    // Clear selection if input is empty
    if (!val || val.trim() === '') {
      startTransition(() => {
        clearLocationSelection();
      });
    } else {
      const trimmed = val.trim();
      if (trimmed) {
        setLocError(null);
        debouncedLocationSearch(trimmed.toUpperCase());
      }
    }
  }, [clearLocationSelection, debouncedLocationSearch, setLocError, startTransition]);

  const triggerLocationSearch = React.useCallback((rawValue) => {
    try { suggestionsControllerRef.current?.abort(); } catch { /* ignore */ }
    const source = typeof rawValue === 'string' ? rawValue : (locInputRef.current?.value || '');
    const valRaw = (source || '').trim();
    if (!valRaw) return false;
    let val = valRaw.toUpperCase();
    const parenIdx = val.indexOf('(');
    if (parenIdx > 0) {
      val = val.slice(0, parenIdx);
    }
    val = val.trim();
    if (!val) return false;
    const firstToken = val.split(/\s+/)[0];
    val = firstToken.replace(/[^A-Z0-9]/g, '');
    if (!val) return false;
    const isFull = /^[A-Z]{3}[0-9]{2}$/.test(val);
    const isPartial4 = /^[A-Z]{3}[0-9]$/.test(val);
    const isPrefix1to3 = /^[A-Z]{1,3}$/.test(val);
    if (!isFull && !isPartial4 && !isPrefix1to3) return false;

    let stored = val;
    if (!isFull) {
      if (stored.length <= 3) {
        stored = stored.replace(/X/g, 'x');
      } else {
        const head = stored.slice(0, 3).replace(/X/g, 'x');
        stored = head + stored.slice(3);
      }
    }

    const code3 = stored.slice(0, 3);
    const cityName = cityNameByCode3?.[code3] || cityNameByCode3?.[code3.toUpperCase()];
    const display = cityName ? `${stored} (${cityName})` : stored;

    setLocSelected(stored);
    setLocInput(stored);
    setLocalInput(display);
    setShowLocationDropdown(false);
    setLocationSuggestions([]);
    setSelectedSuggestionIndex(-1);
    setLocError(null);
    try {
      if (locInputRef.current) locInputRef.current.value = display;
    } catch {
      /* ignore */
    }
    return true;
  }, [cityNameByCode3, locInputRef]);

  const selectLocationSuggestion = React.useCallback((suggestion) => {
    const formattedCode = suggestion.code.toUpperCase().replace(/X/g, 'x');
    triggerLocationSearch(formattedCode);
    setLocationSuggestions([]);
    setShowLocationDropdown(false);
    setSelectedSuggestionIndex(-1);
  }, [triggerLocationSearch]);

  const handleLocationSuggestionSelect = React.useCallback((suggestion) => {
    if (suggestion && suggestion.isPrefixAll) {
      const code3 = String(suggestion.code || '').substring(0, 3).toUpperCase().replace(/X/g, 'x');
      setLocSelected(code3);
      const display = suggestion.city ? `${code3} (${suggestion.city})` : code3;
      setLocalInput(display);
      setLocError(null);
      if (locInputRef.current) {
        try { locInputRef.current.value = display; } catch { /* ignore */ }
      }
      setLocInput(code3);
      setShowLocationDropdown(false);
      setLocationSuggestions([]);
      setSelectedSuggestionIndex(-1);
      return;
    }
    selectLocationSuggestion(suggestion);
    setLocError(null);
  }, [selectLocationSuggestion, setLocError]);

  const handleLocationSearchAction = React.useCallback(() => {
    const rawValue = locInputRef.current?.value ?? '';
    if (!rawValue.trim()) {
      setLocError('Bitte gib einen Standortcode ein');
      return;
    }
    try { suggestionsControllerRef.current?.abort(); } catch { /* ignore */ }
    setLocationSuggestions([]);
    setShowLocationDropdown(false);
    setSelectedSuggestionIndex(-1);
    const succeeded = triggerLocationSearch(rawValue);
    if (!succeeded) {
      setLocError('Unbekannter Standortcode');
    } else {
      setLocError(null);
    }
  }, [triggerLocationSearch]);

  const handleLocationKeyDown = React.useCallback((e) => {
    if (!showLocationDropdown || locationSuggestions.length === 0) {
      if (e.key === 'Enter') {
        const success = triggerLocationSearch(e.target.value);
        if (success) {
          setLocError(null);
          e.preventDefault();
        } else {
          setLocError('Unbekannter Standortcode');
        }
      }
      return;
    }

    // Handle dropdown navigation
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedSuggestionIndex(prev =>
        prev < locationSuggestions.length - 1 ? prev + 1 : 0
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedSuggestionIndex(prev =>
        prev > 0 ? prev - 1 : locationSuggestions.length - 1
      );
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (selectedSuggestionIndex >= 0 && selectedSuggestionIndex < locationSuggestions.length) {
        handleLocationSuggestionSelect(locationSuggestions[selectedSuggestionIndex]);
      }
    } else if (e.key === 'Escape') {
      setShowLocationDropdown(false);
      setSelectedSuggestionIndex(-1);
    }
  }, [showLocationDropdown, locationSuggestions, selectedSuggestionIndex, triggerLocationSearch, handleLocationSuggestionSelect, setLocError]);

  // Cleanup abort controller on unmount
  React.useEffect(() => {
    return () => {
      try { suggestionsControllerRef.current?.abort(); } catch { /* ignore */ }
      suggestionsControllerRef.current = null;
      // Clear any pending timers on unmount
      try { clearTimeout(timeoutRef.current); } catch { }
    };
  }, []);

  // Simple handlers for the new TextField approach
  const handleLocationInputChangeOld = React.useCallback((e) => {
    const val = e.target.value;
    setLocalInput(val);

    // Clear selection if input is empty
    if (!val || val.trim() === '') {
      setLocSelected(null);
      setLocStats({
        totalPhones: 0,
        totalSwitches: 0,
        phonesWithKEM: 0,
        phonesByModel: [],
        phonesByModelJustiz: [],
        phonesByModelJVA: [],
        vlanUsage: [],
        switches: [],
        kemPhones: [],
      });
      setLocStatsLoading(false);
    }
  }, []);

  // Update localInput display when city names are loaded or location changes
  React.useEffect(() => {
    if (locSelected && cityNameByCode3) {
      const code3 = String(locSelected).slice(0, 3);
      const codeUpper = code3.toUpperCase();
      const codeMxx = codeUpper.replace(/X/g, 'x');
      const cityName = cityNameByCode3[code3]
        || cityNameByCode3[codeUpper]
        || cityNameByCode3[codeMxx];
      const displayValue = cityName ? `${locSelected} (${cityName})` : locSelected;

      // Only update if current localInput doesn't already match the expected display
      if (localInput !== displayValue) {
        setLocalInput(displayValue);
        if (locInputRef.current) {
          try { locInputRef.current.value = displayValue; } catch { /* ignore */ }
        }
      }
    }
  }, [cityNameByCode3, localInput, locSelected]);

  // Save selected location to localStorage when it changes
  React.useEffect(() => {
    if (saveStatisticsPrefs) {
      saveStatisticsPrefs({ lastSelectedLocation: locSelected });
    }
  }, [locSelected, saveStatisticsPrefs]);

  const handleKeyDown = React.useCallback((e) => {
    // Use the new location dropdown handler
    handleLocationKeyDown(e);
  }, [handleLocationKeyDown]);

  const handleCityNameChange = React.useCallback((_, value) => {
    if (!value) {
      setCitySearchInput('');
      setLocError(null);
      return;
    }

    setCitySearchInput(value);
    const entry = Object.entries(cityNameByCode3 || {}).find(([, name]) =>
      String(name).toLowerCase() === String(value).toLowerCase()
    );

    if (entry) {
      triggerLocationSearch(entry[0]);
      setLocError(null);
      setCityAutocompleteOpen(false);
    }
  }, [cityNameByCode3, setLocError, triggerLocationSearch, setCityAutocompleteOpen]);

  const clearCitySearchInput = React.useCallback(() => {
    setCitySearchInput('');
    setLocError(null);
    setCityAutocompleteOpen(false);
  }, [setLocError, setCityAutocompleteOpen]);

  const handleCitySearchAction = React.useCallback(() => {
    const term = String(citySearchInput || '').trim();
    if (!term) {
      setLocError('Bitte gib einen Stadtnamen ein');
      setCityAutocompleteOpen(false);
      return;
    }

    const entries = Object.entries(cityNameByCode3 || {});
    const lower = term.toLowerCase();
    const exact = entries.find(([, name]) => String(name).toLowerCase() === lower);
    const partial = entries.find(([, name]) => String(name).toLowerCase().includes(lower));
    const match = exact || partial;

    if (match) {
      const [code, name] = match;
      setCitySearchInput(name);
      triggerLocationSearch(code);
      setLocError(null);
      setCityAutocompleteOpen(false);
    } else {
      setLocError('Keine Stadt gefunden');
      setCityAutocompleteOpen(false);
    }
  }, [cityNameByCode3, citySearchInput, setLocError, triggerLocationSearch, setCityAutocompleteOpen]);

  const filterCityOptions = React.useCallback((options, { inputValue }) => {
    // If no input, show fewer cities
    if (!inputValue.trim()) {
      return options.slice(0, 30);
    }
    // Otherwise filter by input
    const filtered = options.filter(option =>
      option.toLowerCase().includes(inputValue.toLowerCase())
    );
    return filtered.slice(0, 50); // Limit for performance
  }, []);

  const handleSnackbarClose = React.useCallback(() => {
    setSnackbar(prev => ({ ...prev, open: false }));
  }, []);

  React.useEffect(() => {
    // Rehydrate saved statistics preferences on first render
    try {
      const prefs = getStatisticsPrefs?.() || {};
      if (prefs.locSelected) setLocSelected(prefs.locSelected);
      if (typeof prefs.locInput === 'string') setLocInput(prefs.locInput);
      // KPI selections (independent)
      if (Array.isArray(prefs.selectedKpisGlobal)) setSelectedKpisGlobal(prefs.selectedKpisGlobal);
      if (Array.isArray(prefs.selectedKpisLoc)) setSelectedKpisLoc(prefs.selectedKpisLoc);
      // Backward compatibility: a single selectedKpis applies to both
      if (Array.isArray(prefs.selectedKpis)) {
        setSelectedKpisGlobal(prefs.selectedKpis);
        setSelectedKpisLoc(prefs.selectedKpis);
      }
      // Keep Top Locations fixed at Top 10; don't hydrate saved topCount
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
        const r = await fetch('/api/stats/fast/current', { signal: controller.signal });
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
    saveStatisticsPrefs?.({ selectedKpisGlobal });
  }, [selectedKpisGlobal, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    saveStatisticsPrefs?.({ selectedKpisLoc });
  }, [selectedKpisLoc, saveStatisticsPrefs]);

  React.useEffect(() => {
    if (!statsHydratedRef.current) return;
    // Keep Top Locations fixed to Top 10; don't persist topCount
    saveStatisticsPrefs?.({ topExtras, topDays, topKpi });
  }, [topExtras, topDays, topKpi, saveStatisticsPrefs]);

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
    const fixedCount = 10;
    const key = `${fixedCount}|${(topExtras || '').trim()}|${topDays}`;
    if (topLoadedKey === key && (topTimeline.dates || []).length) return;
    let abort = false;
    const controller = new AbortController();
    const h = setTimeout(async () => {
      try {
        setTopTimeline((t) => ({ ...t, loading: true, error: null }));
        const params = new URLSearchParams();
        params.set('count', String(fixedCount));
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
  }, [topExtras, topDays, getStatisticsPrefs, topLoadedKey, topTimeline.dates]);

  // Build per-location line series for selected KPI
  const topSeriesPerKey = React.useMemo(() => {
    const dates = topTimeline.dates || [];
    const byKey = topTimeline.seriesByKey || {};
    const palette = ['#1976d2', '#2e7d32', '#0288d1', '#f57c00', '#6a1b9a', '#d32f2f', '#455a64', '#7b1fa2', '#00796b', '#c2185b'];
    const sortedKeys = [...(topSelectedKeys || [])].sort((a, b) => {
      const asrc = byKey[a]?.[topKpi] || [];
      const bsrc = byKey[b]?.[topKpi] || [];
      const av = Number(asrc.length ? asrc[asrc.length - 1] : 0);
      const bv = Number(bsrc.length ? bsrc[bsrc.length - 1] : 0);
      return bv - av; // desc by latest available value
    });
    return sortedKeys.map((k, idx) => {
      const src = byKey[k]?.[topKpi] || [];
      const aligned = new Array(dates.length).fill(null);
      const copyLen = Math.min(src.length, dates.length);
      for (let i = 0; i < copyLen; i++) {
        aligned[dates.length - 1 - i] = src[src.length - 1 - i];
      }
      return {
        id: k,
        label: (topTimeline.labels && topTimeline.labels[k]) ? topTimeline.labels[k] : k,
        color: palette[idx % palette.length],
        data: aligned,
      };
    });
  }, [topTimeline, topSelectedKeys, topKpi]);

  // Placeholder transparent series to keep chart layout stable when nothing is selected
  const topEmptySeries = React.useMemo(() => (
    [{ id: '__empty', label: '', color: 'rgba(0,0,0,0)', data: new Array((topTimeline.dates || []).length).fill(null) }]
  ), [topTimeline.dates]);

  // Map currently displayed series colors to their keys for chip styling
  const topKeyColorMap = React.useMemo(() => {
    const map = {};
    for (const s of topSeriesPerKey) map[s.id] = s.color;
    return map;
  }, [topSeriesPerKey]);

  // Compute dynamic y-axis bounds for Top 10 chart: zoom to data range
  const topYAxisBounds = React.useMemo(() => {
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    for (const s of topSeriesPerKey) {
      for (const v of s.data) {
        if (v == null) continue; // ignore null placeholders
        const n = Number(v);
        if (!Number.isFinite(n)) continue;
        if (n < min) min = n;
        if (n > max) max = n;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null; // fallback to auto
    if (min === max) {
      if (max <= 0) return { yMin: 0, yMax: 1, ticks: [0, 1] };
      const pad = Math.max(1, Math.round(max * 0.05));
      return { yMin: Math.max(0, max - pad), yMax: max + pad };
    }
    const range = max - min;
    const pad = Math.max(1, Math.round(range * 0.05));
    const yMin = Math.max(0, Math.floor(min - pad));
    const yMax = Math.ceil(max + pad);
    // Build ticks at a nice step
    const targetTicks = 6;
    const rawStep = (yMax - yMin) / Math.max(1, targetTicks);
    const pow10 = Math.pow(10, Math.floor(Math.log10(Math.max(1, rawStep))));
    const steps = [1, 2, 5, 10];
    let step = pow10;
    for (const s of steps) { if (pow10 * s >= rawStep) { step = pow10 * s; break; } }
    const ticks = [];
    const start = Math.ceil(yMin / step) * step;
    const end = Math.floor(yMax / step) * step;
    for (let t = start; t <= end + 1e-9; t += step) ticks.push(Math.round(t));
    return { yMin, yMax, ticks };
  }, [topSeriesPerKey]);

  // Sorted list of location keys for chips: selected first, then by latest KPI value desc, then label asc
  const sortedTopKeysForChips = React.useMemo(() => {
    const keys = topTimeline.keys || [];
    const labels = topTimeline.labels || {};
    const byKey = topTimeline.seriesByKey || {};
    const dates = topTimeline.dates || [];
    const getVal = (k) => {
      const arr = byKey[k]?.[topKpi] || [];
      return Number(arr.length ? arr[arr.length - 1] : 0);
    };
    const getLabel = (k) => (labels && labels[k]) ? labels[k] : k;
    const selectedSet = new Set(topSelectedKeys || []);
    const arr = [...keys];
    arr.sort((a, b) => {
      const aSel = selectedSet.has(a) ? 1 : 0;
      const bSel = selectedSet.has(b) ? 1 : 0;
      if (aSel !== bSel) return bSel - aSel; // selected first
      const av = getVal(a);
      const bv = getVal(b);
      if (av !== bv) return bv - av; // higher value first
      return String(getLabel(a)).localeCompare(String(getLabel(b)));
    });
    return arr;
  }, [topTimeline.keys, topTimeline.labels, topTimeline.seriesByKey, topTimeline.dates, topSelectedKeys, topKpi]);

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

  // Apply locSelected immediately (changed only by Enter or suggestion click)
  React.useEffect(() => {
    setDebouncedLocSelected(locSelected);
  }, [locSelected]);

  // Fetch stats for selected location (use debounced version)
  React.useEffect(() => {
    if (!debouncedLocSelected) {
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
        const q = encodeURIComponent(debouncedLocSelected);
        const r = await fetch(`/api/stats/fast/by_location?q=${q}`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        if (json.success) {
          setLocStats(json.data || {});
        } else {
          setLocStats({ query: debouncedLocSelected, mode: '', totalPhones: 0, totalSwitches: 0, phonesWithKEM: 0, phonesByModel: [], vlanUsage: [], switches: [], kemPhones: [] });
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
  }, [debouncedLocSelected]);

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

  // Reset collapsed state when navigating to By Location view
  React.useEffect(() => {
    const p = (locationRouter?.pathname || '/statistics');
    if (p.startsWith('/statistics/by-location')) setLocTimelineExpanded(false);
  }, [locationRouter?.pathname]);

  // Fetch per-location timeline only when expanded and a location is selected
  React.useEffect(() => {
    if (!debouncedLocSelected) {
      // Reset timeline when no location is selected
      setLocTimeline({ loading: false, error: null, series: [] });
      locTimelineLoadedKeyRef.current = '';
      return;
    }
    if (!locTimelineExpanded) return; // do not fetch while collapsed
    const key = String(debouncedLocSelected).toUpperCase();
    if (locTimelineLoadedKeyRef.current === key && (locTimeline.series || []).length) return;
    let abort = false;
    const controller = new AbortController();
    (async () => {
      try {
        setLocTimeline((t) => ({ ...t, loading: true, error: null }));
        const r = await fetch(`/api/stats/timeline/by_location?q=${encodeURIComponent(debouncedLocSelected)}&limit=0`, { signal: controller.signal });
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
  }, [debouncedLocSelected, locTimelineExpanded]);

  // Placeholder series to keep charts stable when no KPI is selected (Global/Per-location)
  const globalEmptySeries = React.useMemo(() => (
    [{ id: '__empty_global', label: '', color: 'rgba(0,0,0,0)', data: new Array((timeline.series || []).length).fill(null) }]
  ), [timeline.series]);

  const locEmptySeries = React.useMemo(() => (
    [{ id: '__empty_loc', label: '', color: 'rgba(0,0,0,0)', data: new Array((locTimeline.series || []).length).fill(null) }]
  ), [locTimeline.series]);

  // Compute dynamic y-axis for Global timeline; zoom when only one KPI is selected
  const globalYAxisBounds = React.useMemo(() => {
    const items = timeline.series || [];
    if (!Array.isArray(items) || items.length === 0) return null;
    const selected = KPI_DEFS.filter(k => selectedKpisGlobal.includes(k.id));
    if (selected.length === 0) return null;
    if (selected.length === 1) {
      const id = selected[0].id;
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      for (const p of items) {
        const n = Number(p?.metrics?.[id]);
        if (!Number.isFinite(n)) continue;
        if (n < min) min = n;
        if (n > max) max = n;
      }
      if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
      if (min === max) {
        const pad = Math.max(1, Math.round(max * 0.05));
        return { yMin: Math.max(0, max - pad), yMax: max + pad };
      }
      const range = max - min;
      const pad = Math.max(1, Math.round(range * 0.05));
      return { yMin: Math.max(0, Math.floor(min - pad)), yMax: Math.ceil(max + pad) };
    }
    // Multi-KPI: anchor at 0 for comparability
    let max = Number.NEGATIVE_INFINITY;
    for (const k of selected) {
      for (const p of items) {
        const v = p?.metrics?.[k.id];
        if (v == null) continue;
        const n = Number(v);
        if (Number.isFinite(n) && n > max) max = n;
      }
    }
    if (!Number.isFinite(max)) return null;
    const yMin = 0;
    const targetTicks = 6;
    const rawStep = (max - yMin) / Math.max(1, targetTicks);
    const pow10 = Math.pow(10, Math.floor(Math.log10(Math.max(1, rawStep))));
    const steps = [1, 2, 5, 10];
    let step = pow10;
    for (const s of steps) { if (pow10 * s >= rawStep) { step = pow10 * s; break; } }
    const yMax = Math.ceil(max / step) * step;
    return { yMin, yMax };
  }, [timeline.series, KPI_DEFS, selectedKpisGlobal]);

  // Compute dynamic y-axis for Per-Location timeline; zoom when only one KPI is selected
  const locYAxisBounds = React.useMemo(() => {
    const items = locTimeline.series || [];
    if (!Array.isArray(items) || items.length === 0) return null;
    const selected = KPI_DEFS_LOC.filter(k => selectedKpisLoc.includes(k.id));
    if (selected.length === 0) return null;
    if (selected.length === 1) {
      const id = selected[0].id;
      let min = Number.POSITIVE_INFINITY;
      let max = Number.NEGATIVE_INFINITY;
      for (const p of items) {
        const n = Number(p?.metrics?.[id]);
        if (!Number.isFinite(n)) continue;
        if (n < min) min = n;
        if (n > max) max = n;
      }
      if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
      if (min === max) {
        const pad = Math.max(1, Math.round(max * 0.05));
        return { yMin: Math.max(0, max - pad), yMax: max + pad };
      }
      const range = max - min;
      const pad = Math.max(1, Math.round(range * 0.05));
      return { yMin: Math.max(0, Math.floor(min - pad)), yMax: Math.ceil(max + pad) };
    }
    let max = Number.NEGATIVE_INFINITY;
    for (const k of selected) {
      for (const p of items) {
        const v = p?.metrics?.[k.id];
        if (v == null) continue;
        const n = Number(v);
        if (Number.isFinite(n) && n > max) max = n;
      }
    }
    if (!Number.isFinite(max)) return null;
    const yMin = 0;
    const targetTicks = 6;
    const rawStep = (max - yMin) / Math.max(1, targetTicks);
    const pow10 = Math.pow(10, Math.floor(Math.log10(Math.max(1, rawStep))));
    const steps = [1, 2, 5, 10];
    let step = pow10;
    for (const s of steps) { if (pow10 * s >= rawStep) { step = pow10 * s; break; } }
    const yMax = Math.ceil(max / step) * step;
    return { yMin, yMax };
  }, [locTimeline.series, KPI_DEFS_LOC, selectedKpisLoc]);

  // Shared soft chip styling helper for calmer colors
  const softChipSx = React.useCallback((hex) => ({
    fontWeight: 400,
    fontSize: '0.95em',
    px: 1.4,
    py: 0.6,
    borderWidth: '1.5px',
    borderStyle: 'solid',
    borderRadius: 2,
    backgroundColor: (theme) => alpha(hex, theme.palette.mode === 'dark' ? 0.36 : 0.28),
    borderColor: (theme) => alpha(hex, theme.palette.mode === 'dark' ? 0.75 : 0.6),
    color: (theme) => theme.palette.text.primary,
    textShadow: (theme) => theme.palette.mode === 'dark'
      ? '0 0.7px 1.2px rgba(0,0,0,0.75)'
      : '0 0.7px 1.2px rgba(0,0,0,0.35)',
    justifyContent: 'center',
    boxShadow: (theme) => theme.palette.mode === 'dark'
      ? '0 1px 3px rgba(0,0,0,0.4)'
      : '0 1px 3px rgba(0,0,0,0.18)',
    transition: 'background-color 120ms ease, box-shadow 120ms ease',
    '&:hover': {
      backgroundColor: (theme) => alpha(hex, theme.palette.mode === 'dark' ? 0.42 : 0.32),
      boxShadow: (theme) => theme.palette.mode === 'dark'
        ? '0 2px 4px rgba(0,0,0,0.5)'
        : '0 2px 4px rgba(0,0,0,0.22)'
    }
  }), []);

  // Compute a unified width for all General Statistics chips (Total, Justiz, JVA)
  const [genChipWidth, setGenChipWidth] = React.useState(null);
  const measureRef = React.useRef(null);

  // Build all chip labels (as actually rendered) for measurement
  const generalLeftKpis = React.useMemo(() => ([
    { label: 'Switches', value: data.totalSwitches, color: '#d32f2f' },
    { label: 'Locations', value: data.totalLocations, color: '#f57c00' },
    { label: 'Cities', value: data.totalCities, color: '#6a1b9a' },
    { label: 'Phones with KEM', value: data.phonesWithKEM, color: '#2e7d32' },
    { label: 'Total KEMs', value: data.totalKEMs, color: '#2e7d32' },
  ]), [data.totalSwitches, data.totalLocations, data.totalCities, data.phonesWithKEM, data.totalKEMs]);

  const generalJustizKpis = React.useMemo(() => ([
    { label: 'Switches', value: data.justizSwitches, total: data.totalSwitches, color: '#d32f2f' },
    { label: 'Locations', value: data.justizLocations, total: data.totalLocations, color: '#f57c00' },
    { label: 'Cities', value: data.justizCities, total: null, color: '#6a1b9a' },
    { label: 'Phones with KEM', value: data.justizPhonesWithKEM, total: data.phonesWithKEM, color: '#2e7d32' },
    { label: 'Total KEMs', value: data.totalJustizKEMs, total: data.totalKEMs, color: '#2e7d32' },
  ]), [data.justizSwitches, data.justizLocations, data.justizCities, data.justizPhonesWithKEM, data.totalSwitches, data.totalLocations, data.phonesWithKEM, data.totalJustizKEMs, data.totalKEMs]);

  const generalJvaKpis = React.useMemo(() => ([
    { label: 'Switches', value: data.jvaSwitches, total: data.totalSwitches, color: '#d32f2f' },
    { label: 'Locations', value: data.jvaLocations, total: data.totalLocations, color: '#f57c00' },
    { label: 'Cities', value: data.jvaCities, total: null, color: '#6a1b9a' },
    { label: 'Phones with KEM', value: data.jvaPhonesWithKEM, total: data.phonesWithKEM, color: '#2e7d32' },
    { label: 'Total KEMs', value: data.totalJVAKEMs, total: data.totalKEMs, color: '#2e7d32' },
  ]), [data.jvaSwitches, data.jvaLocations, data.jvaCities, data.jvaPhonesWithKEM, data.totalSwitches, data.totalLocations, data.phonesWithKEM, data.totalJVAKEMs, data.totalKEMs]);

  // Measure on data load and window resize
  React.useEffect(() => {
    const measure = () => {
      if (!measureRef.current) return;
      const chips = measureRef.current.querySelectorAll('.MuiChip-root');
      let max = 0;
      chips.forEach((el) => { max = Math.max(max, el.offsetWidth || 0); });
      if (max > 0) setGenChipWidth(max);
    };
    // Small timeout to ensure DOM painted
    const t = setTimeout(measure, 0);
    window.addEventListener('resize', measure);
    return () => { clearTimeout(t); window.removeEventListener('resize', measure); };
  }, [generalLeftKpis, generalJustizKpis, generalJvaKpis, data.totalJustizPhones, data.totalJVAPhones, data.totalPhones]);

  // Sub-view routing flags for left menu navigation
  const curPath = (locationRouter.pathname || '/statistics');
  const isOverview = curPath === '/statistics' || curPath === '/statistics/' || curPath.startsWith('/statistics/overview');
  const isTimelines = curPath.startsWith('/statistics/timelines');
  const isByLocation = curPath.startsWith('/statistics/by-location');
  const isPhonesByModel = curPath.startsWith('/statistics/phones-by-model');

  // Redirect bare /statistics to overview for clarity
  React.useEffect(() => {
    if (curPath === '/statistics' || curPath === '/statistics/') {
      try { navigate('/statistics/overview', { replace: true }); } catch { /* ignore */ }
    }
  }, [curPath, navigate]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
        <Typography variant="h5" fontWeight={700}>Statistics</Typography>
        {fileMeta?.date && (
          <Typography variant="body2" color="text.secondary">from {String(fileMeta.date).slice(0, 10)}</Typography>
        )}
        {(fileMeta?.using_fallback || fileMeta?.is_latest === false) && (
          <Chip
            size="small"
            color="warning"
            variant="outlined"
            label={(() => {
              const d = fileMeta?.date ? String(fileMeta.date).slice(0, 10) : '';
              if (fileMeta?.is_current === false) return `Using historical snapshot (${d})`;
              if (fileMeta?.is_latest === false) return `Latest snapshot unavailable – showing ${d}`;
              return `Using historical snapshot (${d})`;
            })()}
            sx={{
              borderWidth: '1.5px',
              fontWeight: 500,
            }}
          />
        )}
      </Box>

      {error && (
        <Alert severity="info" variant="outlined">{error}</Alert>
      )}

      {/* Two-pane layout: left menu + right content */}
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-start' }}>
        {/* Left menu */}
        <Box sx={{ width: 260, flexShrink: 0 }}>
          <Paper
            variant="outlined"
            sx={{
              p: 1.25,
              borderRadius: 2.5,
              borderColor: 'divider',
              background: (t) => `linear-gradient(180deg, ${alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.08 : 0.06)} 0%, ${alpha(t.palette.background.paper, 1)} 48%, ${alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.06 : 0.04)} 100%)`,
            }}
          >
            <Typography variant="overline" sx={{ px: 1, pt: 0.5, pb: 1, display: 'block', opacity: 0.7, letterSpacing: '0.08em' }}>
              Views
            </Typography>
            <List dense sx={{ py: 0 }}>
              {[
                { to: '/statistics/overview', label: 'Overview', Icon: PublicIcon },
                { to: '/statistics/phones-by-model', label: 'Phones by Model', Icon: PhoneIcon },
                { to: '/statistics/timelines', label: 'Timelines', Icon: TrendingUpIcon },
                { to: '/statistics/by-location', label: 'Statistics by Location', Icon: PlaceIcon },
              ].map((m) => {
                const active = curPath === m.to || (m.to !== '/statistics/overview' && curPath.startsWith(m.to));
                const { Icon } = m;
                return (
                  <ListItem key={m.to} disablePadding sx={{ mb: 0.25 }}>
                    <ListItemButton
                      component={Link}
                      to={m.to}
                      onClick={(e) => { e.preventDefault(); navigate(m.to); }}
                      sx={{
                        position: 'relative',
                        borderRadius: 2,
                        px: 1.25,
                        py: 1,
                        gap: 1,
                        bgcolor: active ? (t) => alpha(t.palette.primary.main, t.palette.mode === 'dark' ? 0.15 : 0.10) : 'transparent',
                        color: active ? 'primary.main' : 'text.secondary',
                        '&:hover': {
                          bgcolor: (t) => alpha(t.palette.primary.main, t.palette.mode === 'dark' ? 0.12 : 0.08),
                          transform: 'translateY(-1px)',
                          transition: 'transform 120ms ease, background-color 120ms ease',
                        },
                        '& .MuiListItemIcon-root': {
                          minWidth: 32,
                          color: active ? 'primary.main' : 'text.disabled',
                        },
                        '& .MuiTypography-root': {
                          fontWeight: active ? 700 : 600,
                          color: active ? 'primary.main' : 'text.primary',
                        },
                        '&::before': active ? {
                          content: '""',
                          position: 'absolute',
                          left: 6,
                          top: '16%',
                          width: 4,
                          height: '68%',
                          borderRadius: 2,
                          backgroundColor: 'primary.main',
                        } : undefined,
                      }}
                    >
                      <ListItemIcon>
                        <Icon fontSize="small" />
                      </ListItemIcon>
                      <Typography variant="body2">{m.label}</Typography>
                    </ListItemButton>
                  </ListItem>
                );
              })}
            </List>
          </Paper>
        </Box>

        {/* Right content */}
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          {/* Overview content */}
          {isOverview && (<>
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
              <Typography variant="subtitle1" sx={{ mb: 3, fontWeight: 600 }}>General Statistics</Typography>

              {/* Begin: previously existing General Statistics markup remains unchanged below */}

              {/* marker: overview-general-start */}

              {/* Modern General Statistics Layout: Total Phones left, Justiz & JVA side-by-side */}
              {/* Modern General Statistics Layout: Total Phones full width, JVA/Justiz right, KPIs full width, percent in parentheses */}
              {/* Modern General Statistics Layout: Total Phones symbol/count left, KPIs below, JVA/Justiz side-by-side right */}
              <Box sx={{
                p: 2.5,
                borderRadius: 3,
                minWidth: 320,
                width: '100%',
                boxShadow: 2,
                background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.10)} 0%, ${alpha(theme.palette.primary.light, 0.04)} 100%)`,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'flex-start',
              }}>
                {/* Hidden measurement container for unified chip width */}
                <Box ref={measureRef} sx={{ position: 'absolute', visibility: 'hidden', pointerEvents: 'none', whiteSpace: 'nowrap', overflow: 'hidden', height: 0 }}>
                  {[...generalLeftKpis.map(k => `${(k.value ?? '-').toLocaleString?.() ?? k.value ?? '-'} ${k.label}`),
                  ...generalJustizKpis.map(k => `${(k.value ?? '-').toLocaleString?.() ?? k.value ?? '-'} ${k.label}${k.total ? ` (${Math.round((Number(k.value || 0) && Number(k.total || 0)) ? (100 * Number(k.value) / Number(k.total)) : 0)}%)` : ''}`),
                  ...generalJvaKpis.map(k => `${(k.value ?? '-').toLocaleString?.() ?? k.value ?? '-'} ${k.label}${k.total ? ` (${Math.round((Number(k.value || 0) && Number(k.total || 0)) ? (100 * Number(k.value) / Number(k.total)) : 0)}%)` : ''}`)
                  ].map((text, i) => (
                    <Chip key={`measure-${i}`} label={text} size="medium" sx={{ fontWeight: 400, fontSize: '0.95em', px: 1.4, py: 0.6 }} />
                  ))}
                </Box>
                {/* Top: Total Phones centered (single line), below: KPIs in 2 centered rows */}
                <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%' }}>
                  {/* Row 1: Label + Count */}
                  <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1.5, justifyContent: 'center', mb: 1 }}>
                    <PublicIcon sx={{ fontSize: '2.0rem', color: 'primary.main' }} />
                    <Typography variant="h6" sx={{ color: 'primary.main', fontWeight: 600 }}>Total Phones</Typography>
                    <Typography variant="h3" fontWeight={800} color="primary.main" sx={{ letterSpacing: '0.03em' }}>{data.totalPhones?.toLocaleString() ?? '-'}</Typography>
                  </Box>
                  {/* Row 2: KPIs split into two centered rows */}
                  {(() => {
                    const items = generalLeftKpis;
                    const mid = Math.ceil(items.length / 2);
                    const rowA = items.slice(0, mid);
                    const rowB = items.slice(mid);
                    return (
                      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, alignItems: 'center', width: '100%' }}>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'nowrap', justifyContent: 'center' }}>
                          {rowA.map((kpi) => (
                            <Chip
                              key={`rowA-${kpi.label}`}
                              label={`${kpi.value?.toLocaleString() ?? '-'} ${kpi.label}`}
                              size="medium"
                              variant="outlined"
                              sx={{
                                ...(softChipSx(kpi.color)),
                                width: genChipWidth || 'auto',
                                minWidth: genChipWidth || 'auto'
                              }}
                            />
                          ))}
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'nowrap', justifyContent: 'center' }}>
                          {rowB.map((kpi) => (
                            <Chip
                              key={`rowB-${kpi.label}`}
                              label={`${kpi.value?.toLocaleString() ?? '-'} ${kpi.label}`}
                              size="medium"
                              variant="outlined"
                              sx={{
                                ...(softChipSx(kpi.color)),
                                width: genChipWidth || 'auto',
                                minWidth: genChipWidth || 'auto'
                              }}
                            />
                          ))}
                        </Box>
                      </Box>
                    );
                  })()}
                </Box>

                {/* Bottom: JVA & Justiz side-by-side */}
                <Box sx={{ display: 'flex', gap: 2, flex: 2, justifyContent: 'stretch', flexWrap: 'wrap', mt: 3, width: '100%' }}>
                  {/* Justiz Card */}
                  <Box sx={{
                    p: 2,
                    borderRadius: 3,
                    boxShadow: 1,
                    background: `linear-gradient(135deg, ${alpha(justiceTheme.primary, 0.18)} 0%, ${alpha(justiceTheme.light, 0.10)} 100%)`,
                    border: `2px solid ${alpha(justiceTheme.primary, 0.18)}`,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    minWidth: 180,
                    flex: 1,
                    width: '100%',
                    maxWidth: 'none',
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <GavelIcon sx={{ fontSize: '1.5rem', color: justiceTheme.primary }} />
                      <Typography variant="subtitle1" fontWeight={700} color={justiceTheme.primary}>Justiz</Typography>
                    </Box>
                    <Typography variant="h5" fontWeight={800} color={justiceTheme.primary} sx={{ mt: 1 }}>{data.totalJustizPhones?.toLocaleString() ?? '-'}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>{data.totalPhones ? `${Math.round(100 * data.totalJustizPhones / data.totalPhones)}% of total` : ''}</Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.7, alignItems: 'center' }}>
                      {generalJustizKpis.map(kpi => {
                        const perc = kpi.total ? ` (${Math.round((Number(kpi.value || 0) && Number(kpi.total || 0)) ? (100 * Number(kpi.value) / Number(kpi.total)) : 0)}%)` : '';
                        return (
                          <Chip
                            key={kpi.label}
                            label={`${kpi.value?.toLocaleString() ?? '-'} ${kpi.label}${perc}`}
                            size="medium"
                            variant="outlined"
                            sx={{
                              ...(softChipSx(kpi.color)),
                              width: genChipWidth || 'auto',
                              minWidth: genChipWidth || 'auto'
                            }}
                          />
                        );
                      })}
                    </Box>
                  </Box>

                  {/* JVA Card */}
                  <Box sx={{
                    p: 2,
                    borderRadius: 3,
                    boxShadow: 1,
                    background: `linear-gradient(135deg, ${alpha(jvaTheme.primary, 0.18)} 0%, ${alpha(jvaTheme.light, 0.10)} 100%)`,
                    border: `2px solid ${alpha(jvaTheme.primary, 0.18)}`,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    minWidth: 180,
                    flex: 1,
                    width: '100%',
                    maxWidth: 'none',
                  }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <SecurityIcon sx={{ fontSize: '1.5rem', color: jvaTheme.primary }} />
                      <Typography variant="subtitle1" fontWeight={700} color={jvaTheme.primary}>JVA</Typography>
                    </Box>
                    <Typography variant="h5" fontWeight={800} color={jvaTheme.primary} sx={{ mt: 1 }}>{data.totalJVAPhones?.toLocaleString() ?? '-'}</Typography>
                    <Typography variant="caption" color="text.secondary" sx={{ mb: 1 }}>{data.totalPhones ? `${Math.round(100 * data.totalJVAPhones / data.totalPhones)}% of total` : ''}</Typography>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.7, alignItems: 'center' }}>
                      {generalJvaKpis.map(kpi => {
                        const perc = kpi.total ? ` (${Math.round((Number(kpi.value || 0) && Number(kpi.total || 0)) ? (100 * Number(kpi.value) / Number(kpi.total)) : 0)}%)` : '';
                        return (
                          <Chip
                            key={kpi.label}
                            label={`${kpi.value?.toLocaleString() ?? '-'} ${kpi.label}${perc}`}
                            size="medium"
                            variant="outlined"
                            sx={{
                              ...(softChipSx(kpi.color)),
                              width: genChipWidth || 'auto',
                              minWidth: genChipWidth || 'auto'
                            }}
                          />
                        );
                      })}
                    </Box>
                  </Box>
                </Box>
              </Box>
            </Paper>

            {false && (<Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.secondary.main}`, backgroundColor: (t) => alpha(t.palette.secondary.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
              <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'secondary.main' }}>Phones by Model</Typography>
              {loading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={28} />
                  ))}
                </Box>
              ) : (
                <Grid container spacing={3} sx={{ alignItems: 'flex-start' }}>
                  {/* Justice institutions Category - ALWAYS show for global stats */}
                  <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
                    <Box sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: justiceTheme.background,
                      border: '1px solid',
                      borderColor: justiceTheme.border,
                      height: '100%'
                    }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: justiceTheme.primary }}>
                        Justice institutions (Justiz)
                      </Typography>
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <List dense sx={{ flex: 1 }}>
                          {/* Total Phones für Justiz */}
                          <ListItem sx={{ py: 0.5, px: 0, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.divider, 0.3), mb: 1 }}>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                  <Chip
                                    label="Total Phones"
                                    size="small"
                                    color="info"
                                    variant="filled"
                                    sx={{ fontWeight: 600 }}
                                  />
                                  <Typography variant="body2" fontWeight={700} sx={{ color: 'info.main', fontSize: '1rem' }}>
                                    {Number(data.totalJustizPhones || 0).toLocaleString()}
                                  </Typography>
                                </Box>
                              }
                            />
                          </ListItem>
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

                        {/* Expandable detailed breakdown by location - grouped by city */}
                        {!loading && (data.phonesByModelJustizDetails || []).length > 0 && (
                          <Accordion sx={{ mt: 1 }} TransitionProps={fastTransitionProps}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PlaceIcon sx={{ fontSize: '1.1rem', color: 'info.main' }} />
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                  View by Location ({(data.phonesByModelJustizDetails || []).length} locations)
                                </Typography>
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={expandAllJustizCities}
                                  sx={{
                                    minWidth: 'auto',
                                    px: 1.5,
                                    py: 0.5,
                                    fontSize: '0.7rem',
                                    borderRadius: 2,
                                    textTransform: 'none',
                                    fontWeight: 500
                                  }}
                                >
                                  Expand All
                                </Button>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={collapseAllJustizCities}
                                  sx={{
                                    minWidth: 'auto',
                                    px: 1.5,
                                    py: 0.5,
                                    fontSize: '0.7rem',
                                    borderRadius: 2,
                                    textTransform: 'none',
                                    fontWeight: 500
                                  }}
                                >
                                  Collapse All
                                </Button>
                              </Box>
                              {/* ...existing code... */}
                            </AccordionDetails>
                            <AccordionDetails sx={{ pt: 0 }}>
                              {groupLocationsByCity(data.phonesByModelJustizDetails || []).map((cityGroup) => (
                                <Accordion
                                  key={`justiz-city-${cityGroup.cityCode}`}
                                  expanded={justizCitiesExpanded[`justiz-city-${cityGroup.cityCode}`] || false}
                                  onChange={(event, isExpanded) => {
                                    setJustizCitiesExpanded(prev => ({
                                      ...prev,
                                      [`justiz-city-${cityGroup.cityCode}`]: isExpanded
                                    }));
                                  }}
                                  TransitionProps={fastTransitionProps}
                                  sx={{
                                    mb: 1,
                                    border: '1px solid',
                                    borderColor: justiceTheme.border,
                                    borderRadius: 1,
                                    backgroundColor: justiceTheme.background,
                                    '&.MuiAccordion-root': {
                                      '&:before': { display: 'none' }
                                    },
                                    '& .MuiAccordionSummary-root': {
                                      transition: 'all 0.1s ease-in-out'
                                    },
                                    '& .MuiAccordionDetails-root': {
                                      transition: 'all 0.1s ease-in-out'
                                    }
                                  }}
                                >
                                  <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    sx={{
                                      backgroundColor: justiceTheme.background,
                                      borderRadius: 1,
                                      minHeight: '40px !important',
                                      '& .MuiAccordionSummary-content': {
                                        margin: '8px 0 !important'
                                      }
                                    }}
                                  >
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <BusinessIcon sx={{ fontSize: '1rem', color: 'info.main' }} />
                                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'info.main' }}>
                                          {cityGroup.cityName} ({cityGroup.cityCode})
                                        </Typography>
                                      </Box>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Chip
                                          label={`${cityGroup.totalCityPhones.toLocaleString()} phones`}
                                          size="small"
                                          color="info"
                                          variant="outlined"
                                          sx={{
                                            fontSize: '0.7rem',
                                            height: '24px',
                                            fontWeight: 600,
                                            backgroundColor: (theme) => alpha(theme.palette.info.main, 0.1),
                                            borderColor: (theme) => theme.palette.info.main,
                                            color: (theme) => theme.palette.info.main
                                          }}
                                        />
                                        <Chip
                                          label={`${cityGroup.locations.length} locations`}
                                          size="small"
                                          variant="outlined"
                                          color="info"
                                          sx={{
                                            fontSize: '0.7rem',
                                            height: '24px',
                                            fontWeight: 500,
                                            mr: 1
                                          }}
                                        />
                                      </Box>
                                    </Box>
                                  </AccordionSummary>
                                  <AccordionDetails sx={{ pt: 1, pb: 1 }}>
                                    <TableContainer sx={{
                                      borderRadius: 2,
                                      overflow: 'hidden',
                                      border: '1px solid',
                                      borderColor: (theme) => alpha(theme.palette.info.main, 0.1)
                                    }}>
                                      <Table size="small" sx={{
                                        '& .MuiTableCell-root': {
                                          py: 0.8,
                                          px: 1.5,
                                          borderBottom: '1px solid',
                                          borderColor: (theme) => alpha(theme.palette.info.main, 0.1)
                                        }
                                      }}>
                                        <TableHead>
                                          <TableRow sx={{
                                            background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette.info.main, 0.12)} 0%, ${alpha(theme.palette.info.main, 0.08)} 100%)`
                                          }}>
                                            <TableCell sx={{
                                              fontWeight: 700,
                                              color: 'info.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Location
                                            </TableCell>
                                            <TableCell align="right" sx={{
                                              fontWeight: 700,
                                              color: 'info.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Total Phones
                                            </TableCell>
                                            <TableCell sx={{
                                              fontWeight: 700,
                                              color: 'info.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Top Models
                                            </TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {cityGroup.locations.map((location) => {
                                            const filteredModels = location.models.filter(m => m.model && m.model !== 'Unknown');
                                            const topModels = filteredModels.slice(0, 3);
                                            return (
                                              <TableRow
                                                key={`justiz-loc-${location.location}`}
                                                sx={{
                                                  '&:hover': {
                                                    backgroundColor: (theme) => alpha(theme.palette.info.main, 0.05),
                                                    transform: 'translateX(2px)',
                                                    transition: 'all 0.2s ease'
                                                  },
                                                  '&:nth-of-type(even)': {
                                                    backgroundColor: (theme) => alpha(theme.palette.info.main, 0.02)
                                                  }
                                                }}
                                              >
                                                <TableCell>
                                                  <Typography variant="body2" fontWeight={600} sx={{ color: 'text.primary' }}>
                                                    {String(location.location).toUpperCase().replace(/X/g, 'x')}
                                                  </Typography>
                                                </TableCell>
                                                <TableCell align="right">
                                                  <Chip
                                                    label={location.totalPhones.toLocaleString()}
                                                    size="small"
                                                    color="primary"
                                                    variant="outlined"
                                                    sx={{
                                                      fontSize: '0.75rem',
                                                      height: '20px',
                                                      minWidth: '45px',
                                                      fontWeight: 500,
                                                      color: 'text.secondary',
                                                      backgroundColor: 'transparent',
                                                      border: '1px solid',
                                                      borderColor: (theme) => alpha(theme.palette.divider, 0.3),
                                                      '&:hover': {
                                                        backgroundColor: (theme) => alpha(theme.palette.action.hover, 0.04)
                                                      }
                                                    }}
                                                  />
                                                </TableCell>
                                                <TableCell>
                                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
                                                    {topModels.map((modelData, index) => (
                                                      <Box
                                                        key={`${String(location.location).toUpperCase().replace(/X/g, 'x')}-${modelData.model}`}
                                                        sx={{
                                                          display: 'flex',
                                                          justifyContent: 'space-between',
                                                          alignItems: 'center',
                                                          backgroundColor: (theme) => alpha(theme.palette.info.main, 0.06),
                                                          borderRadius: 1,
                                                          px: 1,
                                                          py: 0.4,
                                                          border: '1px solid',
                                                          borderColor: (theme) => alpha(theme.palette.info.main, 0.15)
                                                        }}
                                                      >
                                                        <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 600, fontSize: '0.75rem' }}>
                                                          {modelData.model}
                                                        </Typography>
                                                        <Chip
                                                          label={modelData.count.toLocaleString()}
                                                          size="small"
                                                          color="info"
                                                          variant="outlined"
                                                          sx={{
                                                            fontSize: '0.7rem',
                                                            height: '16px',
                                                            minWidth: '30px',
                                                            fontWeight: 400,
                                                            color: 'text.secondary',
                                                            backgroundColor: 'transparent',
                                                            border: '1px solid',
                                                            borderColor: (theme) => alpha(theme.palette.divider, 0.2),
                                                            '&:hover': {
                                                              backgroundColor: (theme) => alpha(theme.palette.action.hover, 0.03)
                                                            }
                                                          }}
                                                        />
                                                      </Box>
                                                    ))}
                                                    {filteredModels.length > 3 && (
                                                      <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', pt: 0.2 }}>
                                                        +{filteredModels.length - 3} more models
                                                      </Typography>
                                                    )}
                                                  </Box>
                                                </TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </AccordionDetails>
                                </Accordion>
                              ))}
                            </AccordionDetails>
                          </Accordion>
                        )}
                      </Box>
                    </Box>
                  </Grid>

                  {/* Correctional Facility Category - ALWAYS show for global stats */}
                  <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
                    <Box sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: jvaTheme.background,
                      border: '1px solid',
                      borderColor: jvaTheme.border,
                      height: '100%'
                    }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: jvaTheme.primary }}>
                        Correctional Facility (JVA)
                      </Typography>
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <List dense sx={{ flex: 1 }}>
                          {/* Total Phones für JVA */}
                          <ListItem sx={{ py: 0.5, px: 0, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.divider, 0.3), mb: 1 }}>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                  <Chip
                                    label="Total Phones"
                                    size="small"
                                    color="warning"
                                    variant="filled"
                                    sx={{ fontWeight: 600 }}
                                  />
                                  <Typography variant="body2" fontWeight={700} sx={{ color: 'warning.main', fontSize: '1rem' }}>
                                    {Number(data.totalJVAPhones || 0).toLocaleString()}
                                  </Typography>
                                </Box>
                              }
                            />
                          </ListItem>
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

                        {/* Expandable detailed breakdown by location - grouped by city */}
                        {!loading && (data.phonesByModelJVADetails || []).length > 0 && (
                          <Accordion sx={{ mt: 1 }} TransitionProps={fastTransitionProps}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PlaceIcon sx={{ fontSize: '1.1rem', color: 'warning.main' }} />
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                  View by Location ({(data.phonesByModelJVADetails || []).length} locations)
                                </Typography>
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={expandAllJvaCities}
                                  sx={{
                                    minWidth: 'auto',
                                    px: 1.5,
                                    py: 0.5,
                                    fontSize: '0.7rem',
                                    borderRadius: 2,
                                    textTransform: 'none',
                                    fontWeight: 500
                                  }}
                                >
                                  Expand All
                                </Button>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  onClick={collapseAllJvaCities}
                                  sx={{
                                    minWidth: 'auto',
                                    px: 1.5,
                                    py: 0.5,
                                    fontSize: '0.7rem',
                                    borderRadius: 2,
                                    textTransform: 'none',
                                    fontWeight: 500
                                  }}
                                >
                                  Collapse All
                                </Button>
                              </Box>
                              {/* ...existing code... */}
                            </AccordionDetails>
                            <AccordionDetails sx={{ pt: 0 }}>
                              {groupLocationsByCity(data.phonesByModelJVADetails || []).map((cityGroup) => (
                                <Accordion
                                  key={`jva-city-${cityGroup.cityCode}`}
                                  expanded={jvaCitiesExpanded[`jva-city-${cityGroup.cityCode}`] || false}
                                  onChange={(event, isExpanded) => {
                                    setJvaCitiesExpanded(prev => ({
                                      ...prev,
                                      [`jva-city-${cityGroup.cityCode}`]: isExpanded
                                    }));
                                  }}
                                  TransitionProps={fastTransitionProps}
                                  sx={{
                                    mb: 1,
                                    border: '1px solid',
                                    borderColor: jvaTheme.border,
                                    borderRadius: 1,
                                    backgroundColor: jvaTheme.background,
                                    '&.MuiAccordion-root': {
                                      '&:before': { display: 'none' }
                                    },
                                    '& .MuiAccordionSummary-root': {
                                      transition: 'all 0.1s ease-in-out'
                                    },
                                    '& .MuiAccordionDetails-root': {
                                      transition: 'all 0.1s ease-in-out'
                                    }
                                  }}
                                >
                                  <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    sx={{
                                      backgroundColor: jvaTheme.background,
                                      borderRadius: 1,
                                      minHeight: '40px !important',
                                      '& .MuiAccordionSummary-content': {
                                        margin: '8px 0 !important'
                                      }
                                    }}
                                  >
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'warning.main' }}>
                                        {cityGroup.cityName} ({cityGroup.cityCode})
                                      </Typography>
                                      <Chip
                                        label={`${cityGroup.totalCityPhones.toLocaleString()} phones`}
                                        size="small"
                                        color="warning"
                                        variant="outlined"
                                        sx={{
                                          fontSize: '0.7rem',
                                          height: '24px',
                                          fontWeight: 600,
                                          backgroundColor: (theme) => alpha(theme.palette.warning.main, 0.1),
                                          borderColor: (theme) => theme.palette.warning.main,
                                          color: (theme) => theme.palette.warning.main,
                                          mr: 1
                                        }}
                                      />
                                    </Box>
                                  </AccordionSummary>
                                  <AccordionDetails sx={{ pt: 1, pb: 1 }}>
                                    <TableContainer sx={{
                                      borderRadius: 2,
                                      overflow: 'hidden',
                                      border: '1px solid',
                                      borderColor: (theme) => alpha(theme.palette.warning.main, 0.1)
                                    }}>
                                      <Table size="small" sx={{
                                        '& .MuiTableCell-root': {
                                          py: 0.8,
                                          px: 1.5,
                                          borderBottom: '1px solid',
                                          borderColor: (theme) => alpha(theme.palette.warning.main, 0.1)
                                        }
                                      }}>
                                        <TableHead>
                                          <TableRow sx={{
                                            background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.12)} 0%, ${alpha(theme.palette.warning.main, 0.08)} 100%)`
                                          }}>
                                            <TableCell sx={{
                                              fontWeight: 700,
                                              color: 'warning.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Location
                                            </TableCell>
                                            <TableCell align="right" sx={{
                                              fontWeight: 700,
                                              color: 'warning.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Total Phones
                                            </TableCell>
                                            <TableCell sx={{
                                              fontWeight: 700,
                                              color: 'warning.main',
                                              fontSize: '0.8rem',
                                              textTransform: 'uppercase',
                                              letterSpacing: '0.5px'
                                            }}>
                                              Top Models
                                            </TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {cityGroup.locations.map((location) => {
                                            const filteredModels = location.models.filter(m => m.model && m.model !== 'Unknown');
                                            const topModels = filteredModels.slice(0, 3);
                                            return (
                                              <TableRow
                                                key={`jva-loc-${location.location}`}
                                                sx={{
                                                  '&:hover': {
                                                    backgroundColor: (theme) => alpha(theme.palette.warning.main, 0.05),
                                                    transform: 'translateX(2px)',
                                                    transition: 'all 0.2s ease'
                                                  },
                                                  '&:nth-of-type(even)': {
                                                    backgroundColor: (theme) => alpha(theme.palette.warning.main, 0.02)
                                                  }
                                                }}
                                              >
                                                <TableCell>
                                                  <Typography variant="body2" fontWeight={600} sx={{ color: 'text.primary' }}>
                                                    {String(location.location).toUpperCase().replace(/X/g, 'x')}
                                                  </Typography>
                                                </TableCell>
                                                <TableCell align="right">
                                                  <Chip
                                                    label={location.totalPhones.toLocaleString()}
                                                    size="small"
                                                    color="warning"
                                                    variant="outlined"
                                                    sx={{
                                                      fontSize: '0.75rem',
                                                      height: '20px',
                                                      minWidth: '45px',
                                                      fontWeight: 500,
                                                      color: 'text.secondary',
                                                      backgroundColor: 'transparent',
                                                      border: '1px solid',
                                                      borderColor: (theme) => alpha(theme.palette.divider, 0.3),
                                                      '&:hover': {
                                                        backgroundColor: (theme) => alpha(theme.palette.action.hover, 0.04)
                                                      }
                                                    }}
                                                  />
                                                </TableCell>
                                                <TableCell>
                                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
                                                    {topModels.map((modelData) => (
                                                      <Box
                                                        key={`${String(location.location).toUpperCase().replace(/X/g, 'x')}-${modelData.model}`}
                                                        sx={{
                                                          display: 'flex',
                                                          justifyContent: 'space-between',
                                                          alignItems: 'center',
                                                          backgroundColor: (theme) => alpha(theme.palette.warning.main, 0.06),
                                                          borderRadius: 1,
                                                          px: 1,
                                                          py: 0.4,
                                                          border: '1px solid',
                                                          borderColor: (theme) => alpha(theme.palette.warning.main, 0.15)
                                                        }}
                                                      >
                                                        <Typography variant="caption" sx={{ color: 'text.primary', fontWeight: 600, fontSize: '0.75rem' }}>
                                                          {modelData.model}
                                                        </Typography>
                                                        <Chip
                                                          label={modelData.count.toLocaleString()}
                                                          size="small"
                                                          color="warning"
                                                          variant="outlined"
                                                          sx={{
                                                            fontSize: '0.7rem',
                                                            height: '16px',
                                                            minWidth: '30px',
                                                            fontWeight: 400,
                                                            color: 'text.secondary',
                                                            backgroundColor: 'transparent',
                                                            border: '1px solid',
                                                            borderColor: (theme) => alpha(theme.palette.divider, 0.2),
                                                            '&:hover': {
                                                              backgroundColor: (theme) => alpha(theme.palette.action.hover, 0.03)
                                                            }
                                                          }}
                                                        />
                                                      </Box>
                                                    ))}
                                                    {filteredModels.length > 3 && (
                                                      <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', pt: 0.2 }}>
                                                        +{filteredModels.length - 3} more models
                                                      </Typography>
                                                    )}
                                                  </Box>
                                                </TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </AccordionDetails>
                                </Accordion>
                              ))}
                            </AccordionDetails>
                          </Accordion>
                        )}
                      </Box>
                    </Box>
                  </Grid>
                </Grid>
              )}
            </Paper>
            )}
          </>)}

          {isPhonesByModel && (
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.secondary.main}`, backgroundColor: (t) => alpha(t.palette.secondary.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
              <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'secondary.main' }}>Phones by Model</Typography>
              {loading ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  {Array.from({ length: 6 }).map((_, i) => (
                    <Skeleton key={i} variant="rectangular" height={28} />
                  ))}
                </Box>
              ) : (
                <Grid container spacing={3} sx={{ alignItems: 'flex-start' }}>
                  {/* Justice institutions Category */}
                  <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
                    <Box sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: justiceTheme.background,
                      border: '1px solid',
                      borderColor: justiceTheme.border,
                      height: '100%'
                    }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: justiceTheme.primary }}>
                        Justice institutions (Justiz)
                      </Typography>
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <List dense sx={{ flex: 1 }}>
                          <ListItem sx={{ py: 0.5, px: 0, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.divider, 0.3), mb: 1 }}>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                  <Chip
                                    label="Total Phones"
                                    size="small"
                                    color="info"
                                    variant="filled"
                                    sx={{ fontWeight: 600 }}
                                  />
                                  <Typography variant="body2" fontWeight={700} sx={{ color: 'info.main', fontSize: '1rem' }}>
                                    {Number(data.totalJustizPhones || 0).toLocaleString()}
                                  </Typography>
                                </Box>
                              }
                            />
                          </ListItem>
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

                        {/* Expanded by default: View by Location (grouped by city) */}
                        {!loading && (data.phonesByModelJustizDetails || []).length > 0 && (
                          <Accordion defaultExpanded sx={{ mt: 1 }} TransitionProps={fastTransitionProps}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PlaceIcon sx={{ fontSize: '1.1rem', color: 'info.main' }} />
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                  View by Location ({(data.phonesByModelJustizDetails || []).length} locations)
                                </Typography>
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Button size="small" variant="outlined" onClick={expandAllJustizCities} sx={{ minWidth: 'auto', px: 1.5, py: 0.5, fontSize: '0.7rem', borderRadius: 2, textTransform: 'none', fontWeight: 500 }}>Expand All</Button>
                                <Button size="small" variant="outlined" onClick={collapseAllJustizCities} sx={{ minWidth: 'auto', px: 1.5, py: 0.5, fontSize: '0.7rem', borderRadius: 2, textTransform: 'none', fontWeight: 500 }}>Collapse All</Button>
                              </Box>
                            </AccordionDetails>
                            <AccordionDetails sx={{ pt: 0 }}>
                              {groupLocationsByCity(data.phonesByModelJustizDetails || []).map((cityGroup) => (
                                <Accordion
                                  key={`justiz-city-${cityGroup.cityCode}`}
                                  expanded={justizCitiesExpanded[`justiz-city-${cityGroup.cityCode}`] || false}
                                  onChange={(event, isExpanded) => {
                                    setJustizCitiesExpanded(prev => ({ ...prev, [`justiz-city-${cityGroup.cityCode}`]: isExpanded }));
                                  }}
                                  TransitionProps={fastTransitionProps}
                                  sx={{ mb: 1, border: '1px solid', borderColor: justiceTheme.border, borderRadius: 1, backgroundColor: justiceTheme.background, '&.MuiAccordion-root': { '&:before': { display: 'none' } } }}
                                >
                                  <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ backgroundColor: justiceTheme.background, borderRadius: 1, minHeight: '40px !important', '& .MuiAccordionSummary-content': { margin: '8px 0 !important' } }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <BusinessIcon sx={{ fontSize: '1rem', color: 'info.main' }} />
                                        <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'info.main' }}>
                                          {(cityGroup.cityName || cityNameByCode3?.[String(cityGroup.cityCode || '').toUpperCase().replace(/X/g, 'x')] || cityNameByCode3?.[String(cityGroup.cityCode || '').toUpperCase()])}
                                          {` (${String(cityGroup.cityCode || '').toUpperCase().replace(/X/g, 'x')})`}
                                        </Typography>
                                      </Box>
                                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                        <Chip label={`${cityGroup.totalCityPhones.toLocaleString()} phones`} size="small" color="info" variant="outlined" sx={{ fontSize: '0.7rem', height: '24px', fontWeight: 600 }} />
                                        <Chip label={`${cityGroup.locations.length} locations`} size="small" variant="outlined" color="info" sx={{ fontSize: '0.7rem', height: '24px', fontWeight: 500, mr: 1 }} />
                                      </Box>
                                    </Box>
                                  </AccordionSummary>
                                  <AccordionDetails sx={{ pt: 1, pb: 1 }}>
                                    <TableContainer sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: (theme) => alpha(theme.palette.info.main, 0.1) }}>
                                      <Table size="small" sx={{ '& .MuiTableCell-root': { py: 0.8, px: 1.5, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.info.main, 0.1) } }}>
                                        <TableHead>
                                          <TableRow sx={{ background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette.info.main, 0.12)} 0%, ${alpha(theme.palette.info.main, 0.08)} 100%)` }}>
                                            <TableCell sx={{ fontWeight: 700, color: 'info.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Location</TableCell>
                                            <TableCell align="right" sx={{ fontWeight: 700, color: 'info.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Phones</TableCell>
                                            <TableCell sx={{ fontWeight: 700, color: 'info.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Top Models</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {cityGroup.locations.map((location) => {
                                            const filteredModels = location.models.filter(m => m.model && m.model !== 'Unknown');
                                            const topModels = filteredModels.slice(0, 3);
                                            return (
                                              <TableRow key={`justiz-loc-${location.location}`}>
                                                <TableCell><Typography variant="body2" fontWeight={600}>{String(location.location).toUpperCase().replace(/X/g, 'x')}</Typography></TableCell>
                                                <TableCell align="right"><Chip label={location.totalPhones.toLocaleString()} size="small" color="primary" variant="outlined" /></TableCell>
                                                <TableCell>
                                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
                                                    {topModels.map((modelData) => (
                                                      <Box key={`${String(location.location).toUpperCase().replace(/X/g, 'x')}-${modelData.model}`} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                        <Typography variant="caption" sx={{ fontWeight: 600 }}>{modelData.model}</Typography>
                                                        <Chip label={modelData.count.toLocaleString()} size="small" color="info" variant="outlined" />
                                                      </Box>
                                                    ))}
                                                    {filteredModels.length > 3 && (
                                                      <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', pt: 0.2 }}>+{filteredModels.length - 3} more models</Typography>
                                                    )}
                                                  </Box>
                                                </TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </AccordionDetails>
                                </Accordion>
                              ))}
                            </AccordionDetails>
                          </Accordion>
                        )}
                      </Box>
                    </Box>
                  </Grid>

                  {/* JVA Category */}
                  <Grid item xs={12} md={6} sx={{ display: 'flex', flexDirection: 'column', height: 'fit-content' }}>
                    <Box sx={{
                      p: 2,
                      borderRadius: 2,
                      backgroundColor: jvaTheme.background,
                      border: '1px solid',
                      borderColor: jvaTheme.border,
                      height: '100%'
                    }}>
                      <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600, color: jvaTheme.primary }}>
                        Correctional Facility (JVA)
                      </Typography>
                      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                        <List dense sx={{ flex: 1 }}>
                          <ListItem sx={{ py: 0.5, px: 0, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.divider, 0.3), mb: 1 }}>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                  <Chip
                                    label="Total Phones"
                                    size="small"
                                    color="warning"
                                    variant="filled"
                                    sx={{ fontWeight: 600 }}
                                  />
                                  <Typography variant="body2" fontWeight={700} sx={{ color: 'warning.main', fontSize: '1rem' }}>
                                    {Number(data.totalJVAPhones || 0).toLocaleString()}
                                  </Typography>
                                </Box>
                              }
                            />
                          </ListItem>
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

                        {/* Expanded by default: View by Location (grouped by city) */}
                        {!loading && (data.phonesByModelJVADetails || []).length > 0 && (
                          <Accordion defaultExpanded sx={{ mt: 1 }} TransitionProps={fastTransitionProps}>
                            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <PlaceIcon sx={{ fontSize: '1.1rem', color: 'warning.main' }} />
                                <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                                  View by Location ({(data.phonesByModelJVADetails || []).length} locations)
                                </Typography>
                              </Box>
                            </AccordionSummary>
                            <AccordionDetails>
                              <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                <Button size="small" variant="outlined" onClick={expandAllJvaCities} sx={{ minWidth: 'auto', px: 1.5, py: 0.5, fontSize: '0.7rem', borderRadius: 2, textTransform: 'none', fontWeight: 500 }}>Expand All</Button>
                                <Button size="small" variant="outlined" onClick={collapseAllJvaCities} sx={{ minWidth: 'auto', px: 1.5, py: 0.5, fontSize: '0.7rem', borderRadius: 2, textTransform: 'none', fontWeight: 500 }}>Collapse All</Button>
                              </Box>
                            </AccordionDetails>
                            <AccordionDetails sx={{ pt: 0 }}>
                              {groupLocationsByCity(data.phonesByModelJVADetails || []).map((cityGroup) => (
                                <Accordion
                                  key={`jva-city-${cityGroup.cityCode}`}
                                  expanded={jvaCitiesExpanded[`jva-city-${cityGroup.cityCode}`] || false}
                                  onChange={(event, isExpanded) => {
                                    setJvaCitiesExpanded(prev => ({ ...prev, [`jva-city-${cityGroup.cityCode}`]: isExpanded }));
                                  }}
                                  TransitionProps={fastTransitionProps}
                                  sx={{ mb: 1, border: '1px solid', borderColor: jvaTheme.border, borderRadius: 1, backgroundColor: jvaTheme.background, '&.MuiAccordion-root': { '&:before': { display: 'none' } } }}
                                >
                                  <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ backgroundColor: jvaTheme.background, borderRadius: 1, minHeight: '40px !important', '& .MuiAccordionSummary-content': { margin: '8px 0 !important' } }}>
                                    <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'warning.main' }}>
                                        {(cityGroup.cityName || cityNameByCode3?.[String(cityGroup.cityCode || '').toUpperCase().replace(/X/g, 'x')] || cityNameByCode3?.[String(cityGroup.cityCode || '').toUpperCase()])}
                                        {` (${String(cityGroup.cityCode || '').toUpperCase().replace(/X/g, 'x')})`}
                                      </Typography>
                                      <Chip label={`${cityGroup.totalCityPhones.toLocaleString()} phones`} size="small" color="warning" variant="outlined" sx={{ fontSize: '0.7rem', height: '24px', fontWeight: 600, mr: 1 }} />
                                    </Box>
                                  </AccordionSummary>
                                  <AccordionDetails sx={{ pt: 1, pb: 1 }}>
                                    <TableContainer sx={{ borderRadius: 2, overflow: 'hidden', border: '1px solid', borderColor: (theme) => alpha(theme.palette.warning.main, 0.1) }}>
                                      <Table size="small" sx={{ '& .MuiTableCell-root': { py: 0.8, px: 1.5, borderBottom: '1px solid', borderColor: (theme) => alpha(theme.palette.warning.main, 0.1) } }}>
                                        <TableHead>
                                          <TableRow sx={{ background: (theme) => `linear-gradient(135deg, ${alpha(theme.palette.warning.main, 0.12)} 0%, ${alpha(theme.palette.warning.main, 0.08)} 100%)` }}>
                                            <TableCell sx={{ fontWeight: 700, color: 'warning.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Location</TableCell>
                                            <TableCell align="right" sx={{ fontWeight: 700, color: 'warning.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Phones</TableCell>
                                            <TableCell sx={{ fontWeight: 700, color: 'warning.main', fontSize: '0.8rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Top Models</TableCell>
                                          </TableRow>
                                        </TableHead>
                                        <TableBody>
                                          {cityGroup.locations.map((location) => {
                                            const filteredModels = location.models.filter(m => m.model && m.model !== 'Unknown');
                                            const topModels = filteredModels.slice(0, 3);
                                            return (
                                              <TableRow key={`jva-loc-${location.location}`}>
                                                <TableCell><Typography variant="body2" fontWeight={600}>{String(location.location).toUpperCase().replace(/X/g, 'x')}</Typography></TableCell>
                                                <TableCell align="right"><Chip label={location.totalPhones.toLocaleString()} size="small" color="warning" variant="outlined" /></TableCell>
                                                <TableCell>
                                                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
                                                    {topModels.map((modelData) => (
                                                      <Box key={`${String(location.location).toUpperCase().replace(/X/g, 'x')}-${modelData.model}`} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                        <Typography variant="caption" sx={{ fontWeight: 600 }}>{modelData.model}</Typography>
                                                        <Chip label={modelData.count.toLocaleString()} size="small" color="warning" variant="outlined" />
                                                      </Box>
                                                    ))}
                                                    {filteredModels.length > 3 && (
                                                      <Typography variant="caption" sx={{ color: 'text.secondary', fontStyle: 'italic', textAlign: 'center', pt: 0.2 }}>+{filteredModels.length - 3} more models</Typography>
                                                    )}
                                                  </Box>
                                                </TableCell>
                                              </TableRow>
                                            );
                                          })}
                                        </TableBody>
                                      </Table>
                                    </TableContainer>
                                  </AccordionDetails>
                                </Accordion>
                              ))}
                            </AccordionDetails>
                          </Accordion>
                        )}
                      </Box>
                    </Box>
                  </Grid>
                </Grid>
              )}
            </Paper>
          )}
          {isByLocation && (
            <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.info.main}`, backgroundColor: (t) => alpha(t.palette.info.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
              <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'info.main' }}>Statistics by Location</Typography>

              {/* Two search fields side by side */}
              <Grid container spacing={2} sx={{ mb: 2 }}>
                {/* Location Code Search with Dropdown */}
                <Grid item xs={12} md={6} sx={{ position: 'relative' }}>
                  <TextField
                    label="Search by Location Code"
                    placeholder="Enter location code (e.g., AUG01, NUE02)"
                    size="small"
                    fullWidth
                    defaultValue={localInput}
                    inputRef={locInputRef}
                    onChange={handleLocationInputChange}
                    onKeyDown={handleKeyDown}
                    error={!!locError}
                    helperText={locError || (locInput && !locSelected ? "Drücke Enter oder tippe auf das Suchsymbol" : "")}
                    InputProps={{
                      startAdornment: (
                        <InputAdornment position="start">
                          <SearchIcon sx={{ color: 'action.disabled' }} />
                        </InputAdornment>
                      ),
                      endAdornment: (
                        <InputAdornment position="end">
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mr: -0.5 }}>
                            {locSelected && (
                              <Tooltip title="Auswahl löschen">
                                <IconButton
                                  aria-label="Clear location selection"
                                  size="small"
                                  edge="end"
                                  onClick={clearLocationSelection}
                                  sx={{
                                    width: 32,
                                    height: 32,
                                    color: 'text.secondary',
                                    '&:hover': {
                                      color: 'primary.main',
                                      backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.2 : 0.08),
                                    }
                                  }}
                                >
                                  <CloseIcon fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            )}
                            <Tooltip title="Standort suchen">
                              <span>
                                <IconButton
                                  aria-label="Search location"
                                  size="small"
                                  edge="end"
                                  color="primary"
                                  onClick={handleLocationSearchAction}
                                  disabled={locationActionLoading}
                                  sx={{
                                    width: 34,
                                    height: 34,
                                    borderRadius: 1.5,
                                    backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.32 : 0.14),
                                    color: 'primary.main',
                                    transition: 'background-color 120ms ease, transform 120ms ease',
                                    '&:hover': {
                                      backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.38 : 0.2),
                                      transform: 'translateY(-1px)'
                                    },
                                    '&.Mui-disabled': {
                                      backgroundColor: (theme) => alpha(theme.palette.action.disabledBackground, 0.9),
                                      color: (theme) => theme.palette.action.disabled,
                                      transform: 'none'
                                    }
                                  }}
                                >
                                  {locationActionLoading ? (
                                    <CircularProgress size={18} thickness={5} sx={{ color: 'inherit' }} />
                                  ) : (
                                    <SearchIcon fontSize="small" />
                                  )}
                                </IconButton>
                              </span>
                            </Tooltip>
                          </Box>
                        </InputAdornment>
                      ),
                    }}
                  />

                  {/* Location Suggestions Dropdown */}
                  {showLocationDropdown && (() => {
                    const inputVal = (locInputRef.current && typeof locInputRef.current.value === 'string') ? locInputRef.current.value.trim() : '';
                    const three = /^[a-zA-Z]{3}$/.test(inputVal);
                    return three || (locationSuggestions.length > 0);
                  })() && (
                      <Paper
                        elevation={8}
                        sx={{
                          position: 'absolute',
                          top: 'calc(100% + 2px)',
                          left: '2%',
                          width: '98%',
                          minWidth: '320px',
                          maxWidth: 'none',
                          zIndex: 1300,
                          maxHeight: '280px',
                          overflow: 'auto',
                          borderRadius: 2,
                          border: (theme) => `1px solid ${theme.palette.divider}`,
                          boxShadow: (theme) =>
                            theme.palette.mode === 'dark'
                              ? '0 8px 32px rgba(0,0,0,0.5)'
                              : '0 8px 32px rgba(0,0,0,0.12)',
                        }}
                      >
                        {(() => {
                          // Redundant safety: render a sticky prefix item at the top when input is exactly 3 letters
                          const inputVal = (locInputRef.current && typeof locInputRef.current.value === 'string') ? locInputRef.current.value.trim() : '';
                          const three = /^[a-zA-Z]{3}$/.test(inputVal);
                          if (!three) return null;
                          const codeUpper = inputVal.toUpperCase();
                          const codeMxx = codeUpper.replace(/X/g, 'x');
                          const city = cityNameByCode3?.[codeMxx] || cityNameByCode3?.[codeUpper];
                          // If merged array already starts with our synthetic item, skip
                          const first = locationSuggestions[0];
                          const firstIsSamePrefix = first && first.isPrefixAll && String(first.code || '').toUpperCase().replace(/X/g, 'x') === codeMxx;
                          if (firstIsSamePrefix) return null;
                          return (
                            <Box
                              key={`${codeMxx}__prefix_top`}
                              onClick={() => handleLocationSuggestionSelect({ code: codeMxx, city, isPrefixAll: true })}
                              sx={{
                                px: 2,
                                py: 1.5,
                                cursor: 'pointer',
                                backgroundColor: (theme) => theme.palette.action.hover,
                                borderBottom: '1px solid',
                                borderBottomColor: (theme) => theme.palette.divider,
                                transition: 'background-color 0.15s ease',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1.5,
                              }}
                            >
                              <Box
                                sx={{
                                  width: 32,
                                  height: 32,
                                  borderRadius: '50%',
                                  backgroundColor: (theme) => theme.palette.primary.main,
                                  color: 'white',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: '14px',
                                  fontWeight: 'bold',
                                  flexShrink: 0,
                                }}
                              >
                                {codeMxx}
                              </Box>
                              <Box sx={{ flex: 1, minWidth: 0 }}>
                                <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary', mb: 0.25 }}>
                                  {city ? `${codeMxx} ${city}` : codeMxx}
                                </Typography>
                                <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.75rem' }}>
                                  All locations in this city
                                </Typography>
                              </Box>
                            </Box>
                          );
                        })()}
                        {locationSuggestions.map((suggestion, index) => (
                          <Box
                            key={suggestion.code.toUpperCase().replace(/X/g, 'x')}
                            onClick={() => handleLocationSuggestionSelect(suggestion)}
                            sx={{
                              px: 2,
                              py: 1.5,
                              cursor: 'pointer',
                              backgroundColor: selectedSuggestionIndex === index
                                ? (theme) => theme.palette.action.selected
                                : 'transparent',
                              '&:hover': {
                                backgroundColor: (theme) => theme.palette.action.hover,
                              },
                              borderBottom: index < locationSuggestions.length - 1 ? '1px solid' : 'none',
                              borderBottomColor: (theme) => theme.palette.divider,
                              transition: 'background-color 0.15s ease',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 1.5,
                            }}
                          >
                            {/* Location icon */}
                            <Box
                              sx={{
                                width: 32,
                                height: 32,
                                borderRadius: '50%',
                                backgroundColor: (theme) => theme.palette.primary.main,
                                color: 'white',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '14px',
                                fontWeight: 'bold',
                                flexShrink: 0,
                              }}
                            >
                              {suggestion.code.substring(0, 3).toUpperCase().replace(/X/g, 'x')}
                            </Box>
                            {/* Location details */}
                            <Box sx={{ flex: 1, minWidth: 0 }}>
                              <Typography
                                variant="body2"
                                sx={{
                                  fontWeight: 600,
                                  color: 'text.primary',
                                  mb: 0.25,
                                }}
                              >
                                {(() => {
                                  const code = suggestion.code.toUpperCase().replace(/X/g, 'x');
                                  if (!suggestion.isPrefixAll) return code;
                                  const city = suggestion.city || cityNameByCode3?.[code] || cityNameByCode3?.[code.toUpperCase()];
                                  return city ? `${code} ${city}` : code;
                                })()}
                              </Typography>
                              {suggestion.city && !suggestion.isPrefixAll && (
                                <Typography
                                  variant="caption"
                                  sx={{
                                    color: 'text.secondary',
                                    fontSize: '0.75rem',
                                  }}
                                >
                                  📍 {suggestion.city}
                                </Typography>
                              )}
                              {suggestion.isPrefixAll && (
                                <Typography
                                  variant="caption"
                                  sx={{ color: 'text.secondary', fontSize: '0.75rem' }}
                                >
                                  All locations in this city
                                </Typography>
                              )}
                            </Box>
                          </Box>
                        ))}
                      </Paper>
                    )}
                </Grid>

                {/* City Name Search */}
                <Grid item xs={12} md={6}>
                  <Autocomplete
                    options={Object.values(cityNameByCode3).sort()}
                    freeSolo={false}
                    openOnFocus={false}
                    disableClearable
                    forcePopupIcon={false}
                    disableListWrap
                    sx={{ width: '100%' }}
                    inputValue={citySearchInput}
                    onInputChange={(event, value, reason) => {
                      if (reason === 'input' || reason === 'clear' || reason === 'reset') {
                        setCitySearchInput(value || '');
                        if (!value) {
                          setLocError(null);
                        }
                      }
                      if (reason === 'input') {
                        setCityAutocompleteOpen(Boolean(value));
                      } else if (reason === 'clear' || reason === 'reset') {
                        setCityAutocompleteOpen(false);
                      }
                    }}
                    onChange={handleCityNameChange}
                    filterOptions={filterCityOptions}
                    getOptionLabel={(option) => option}
                    open={cityAutocompleteOpen}
                    onOpen={() => setCityAutocompleteOpen(true)}
                    onClose={() => setCityAutocompleteOpen(false)}
                    slotProps={{
                      paper: { sx: { maxHeight: 200, overflowY: 'auto' } },
                      listbox: { sx: { maxHeight: 160, overflowY: 'auto' } },
                    }}
                    ListboxProps={{ style: { maxHeight: 160, overflowY: 'auto' } }}
                    renderOption={(props, option) => {
                      const cityCode = Object.entries(cityNameByCode3).find(([code, name]) => name === option)?.[0];
                      const { key, ...otherProps } = props;
                      return (
                        <li key={key} {...otherProps}>
                          <Box>
                            <Typography variant="body2">{option}</Typography>
                            {cityCode && (
                              <Typography variant="caption" color="text.secondary">Code: {cityCode}</Typography>
                            )}
                          </Box>
                        </li>
                      );
                    }}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Search by City Name"
                        placeholder="Type city name"
                        size="small"
                        fullWidth
                        onFocus={() => setCityAutocompleteOpen(true)}
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mr: -0.5 }}>
                              {citySearchInput && (
                                <Tooltip title="Eingabe löschen">
                                  <IconButton
                                    aria-label="Clear city search"
                                    size="small"
                                    edge="end"
                                    onClick={clearCitySearchInput}
                                    sx={{
                                      width: 32,
                                      height: 32,
                                      color: 'text.secondary',
                                      '&:hover': {
                                        color: 'primary.main',
                                        backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.2 : 0.08),
                                      }
                                    }}
                                  >
                                    <CloseIcon fontSize="small" />
                                  </IconButton>
                                </Tooltip>
                              )}
                              <Tooltip title="Stadt suchen">
                                <span>
                                  <IconButton
                                    aria-label="Search by city"
                                    size="small"
                                    edge="end"
                                    color="primary"
                                    onClick={handleCitySearchAction}
                                    sx={{
                                      width: 34,
                                      height: 34,
                                      borderRadius: 1.5,
                                      backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.32 : 0.14),
                                      color: 'primary.main',
                                      transition: 'background-color 120ms ease, transform 120ms ease',
                                      '&:hover': {
                                        backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.38 : 0.2),
                                        transform: 'translateY(-1px)'
                                      },
                                      '&.Mui-disabled': {
                                        backgroundColor: (theme) => alpha(theme.palette.action.disabledBackground, 0.9),
                                        color: (theme) => theme.palette.action.disabled,
                                        transform: 'none'
                                      }
                                    }}
                                  >
                                    <SearchIcon fontSize="small" />
                                  </IconButton>
                                </span>
                              </Tooltip>
                            </Box>
                          ),
                        }}
                      />
                    )}
                  />
                </Grid>
              </Grid>

              {locError && (
                <Box sx={{ mb: 2 }}>
                  <Alert severity="warning" variant="outlined">{locError}</Alert>
                </Box>
              )}

              <Grid container spacing={2} sx={{ mb: 1 }}>
                <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Phones" value={locStats.totalPhones} loading={locStatsLoading} /></Grid>
                <Grid item xs={12} sm={6} md={3}><StatCard tone="info" title="Total Switches" value={locStats.totalSwitches} loading={locStatsLoading} /></Grid>
                <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={locStats.phonesWithKEM} loading={locStatsLoading} /></Grid>
              </Grid>

              {/* Subtle hint when city prefix is selected */}
              {locStats?.mode === 'prefix' && locStats?.query && (
                <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary">
                    Statistics by Location
                  </Typography>
                  <Chip
                    size="small"
                    color="default"
                    variant="outlined"
                    label={`All locations matching ${locStats.query}*`}
                  />
                </Box>
              )}

              {/* Additional per-location details */}
              <Box sx={{ mt: 2 }}>
                {/* Phones by Model - Full Width */}
                <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: 'secondary.main' }}>Phones by Model</Typography>
                {locStatsLoading ? (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Skeleton key={i} variant="rectangular" height={28} />
                    ))}
                  </Box>
                ) : (
                  <Grid container spacing={2}>
                    {/* Justice institutions Box */}
                    {(!locSelected || locSelected.length === 3 || isJusticeLocation(locSelected)) &&
                      (locStats.phonesByModelJustiz || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length > 0 && (
                        <Grid item xs={12} md={4}>
                          <Box sx={{
                            p: 1.5,
                            borderRadius: 1,
                            backgroundColor: justiceTheme.background,
                            border: '1px solid',
                            borderColor: justiceTheme.border,
                            height: 'fit-content'
                          }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, color: justiceTheme.primary, mb: 0.5 }}>
                              Justice institutions (Justiz)
                            </Typography>
                            <List dense sx={{ mb: 0 }}>
                              {(locStats.phonesByModelJustiz || [])
                                .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                                .slice(0, 5)
                                .map(({ model, count }) => {
                                  const label = String(model);
                                  const lower = label.toLowerCase();
                                  let color = 'default';
                                  if (lower.includes('kem')) color = 'success';
                                  else if (lower.includes('conference')) color = 'info';
                                  else if (lower.includes('wireless')) color = 'warning';
                                  else color = 'primary';
                                  return (
                                    <ListItem key={`justiz-${model}`} sx={{ py: 0.2, px: 0 }}>
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
                          </Box>
                        </Grid>
                      )}

                    {/* JVA Box */}
                    {(!locSelected || locSelected.length === 3 || isJVALocation(locSelected)) &&
                      (locStats.phonesByModelJVA || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length > 0 && (
                        <Grid item xs={12} md={4}>
                          <Box sx={{
                            p: 1.5,
                            borderRadius: 1,
                            backgroundColor: jvaTheme.background,
                            border: '1px solid',
                            borderColor: jvaTheme.border,
                            height: 'fit-content'
                          }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, color: jvaTheme.primary, mb: 0.5 }}>
                              Correctional Facility (JVA)
                            </Typography>
                            <List dense>
                              {(locStats.phonesByModelJVA || [])
                                .filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model))
                                .slice(0, 5)
                                .map(({ model, count }) => {
                                  const label = String(model);
                                  const lower = label.toLowerCase();
                                  let color = 'default';
                                  if (lower.includes('kem')) color = 'success';
                                  else if (lower.includes('conference')) color = 'info';
                                  else if (lower.includes('wireless')) color = 'error';
                                  else color = 'warning';
                                  return (
                                    <ListItem key={`jva-${model}`} sx={{ py: 0.2, px: 0 }}>
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
                          </Box>
                        </Grid>
                      )}

                    {/* VLAN Usage Box */}
                    {(locStats.vlanUsage || []).length > 0 && (
                      <Grid item xs={12} md={4}>
                        <Box sx={{
                          p: 1.5,
                          borderRadius: 1,
                          backgroundColor: (theme) => alpha(theme.palette.primary.light, theme.palette.mode === 'dark' ? 0.08 : 0.05),
                          border: '1px solid',
                          borderColor: (theme) => alpha(theme.palette.primary.main, 0.2),
                          height: 'fit-content'
                        }}>
                          <Typography variant="body2" sx={{ fontWeight: 600, color: 'primary.main', mb: 0.5 }}>
                            VLAN Usage
                          </Typography>
                          <List dense>
                            {(locStats.vlanUsage || []).slice(0, 5).map(({ vlan, count }) => {
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
                                <ListItem key={`vlan-${vlan}`} sx={{ py: 0.2, px: 0 }}>
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
                        </Box>
                      </Grid>
                    )}
                  </Grid>
                )}
              </Box>

              <Accordion
                disableGutters
                elevation={0}
                TransitionProps={fastTransitionProps}
                sx={{
                  border: '1px solid',
                  borderColor: (t) => alpha(t.palette.primary.main, 0.2),
                  borderRadius: 1,
                  '&:before': { display: 'none' },
                  mt: 2,
                  mb: 1,
                  backgroundColor: (t) => alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.04 : 0.03),
                  '& .MuiAccordionSummary-root': { transition: 'all 0.1s ease-in-out' },
                  '& .MuiAccordionDetails-root': { transition: 'all 0.1s ease-in-out' }
                }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  sx={{ minHeight: '40px !important', '& .MuiAccordionSummary-content': { m: '8px 0 !important' } }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <RouterIcon sx={{ fontSize: '1.1rem', color: 'primary.main' }} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'primary.main' }}>
                        Switches {(() => {
                          const q = String(locStats?.query || '').toUpperCase();
                          // Prefix mode (e.g., ABX) -> show city name with code
                          if (locStats?.mode === 'prefix' && q.length === 3 && cityNameByCode3[q]) {
                            return `in ${cityNameByCode3[q]} (${q})`;
                          }
                          // Exact location (e.g., ABX01) -> show code with city name if available
                          if (q && q.length === 5) {
                            const cityName = cityNameByCode3[q.slice(0, 3)] || '';
                            return cityName ? `${q} (${cityName})` : q;
                          }
                          return 'at this Location';
                        })()}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      {(() => {
                        const total = Number(
                          (locStats.totalSwitches ?? ((locStats.switchDetails && locStats.switchDetails.length)
                            ? locStats.switchDetails.length
                            : (locStats.switches || []).length)) || 0
                        );
                        return (
                          <Chip
                            label={`${total.toLocaleString()} switches`}
                            size="small"
                            color="primary"
                            variant="outlined"
                            sx={{
                              fontSize: '0.7rem',
                              height: '24px',
                              fontWeight: 600,
                              backgroundColor: (t) => alpha(t.palette.primary.main, 0.08),
                              borderColor: (t) => t.palette.primary.main,
                              color: (t) => t.palette.primary.main
                            }}
                          />
                        );
                      })()}
                      {(() => {
                        const vlanSet = new Set();
                        const src = (locStats.switchDetails && locStats.switchDetails.length > 0) ? locStats.switchDetails : (locStats.switches || []);
                        (src || []).forEach(sw => (sw.vlans || []).forEach(v => {
                          const label = v?.vlan;
                          if (label !== undefined && label !== null && String(label).trim() !== '') vlanSet.add(String(label).trim());
                        }));
                        const cnt = vlanSet.size;
                        if (!cnt) return null;
                        return (
                          <Chip
                            label={`${cnt} VLANs`}
                            size="small"
                            color="primary"
                            variant="outlined"
                            sx={{
                              fontSize: '0.7rem',
                              height: '24px',
                              fontWeight: 600,
                              backgroundColor: (t) => alpha(t.palette.primary.main, 0.08),
                              borderColor: (t) => t.palette.primary.main,
                              color: (t) => t.palette.primary.main
                            }}
                          />
                        );
                      })()}
                    </Box>
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  {locStatsLoading ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} variant="rectangular" height={24} />
                      ))}
                    </Box>
                  ) : (
                    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1, border: '1px solid', borderColor: (t) => alpha(t.palette.primary.main, 0.1) }}>
                      <Table size="small" sx={{
                        '& .MuiTableCell-root': {
                          py: 0.8,
                          px: 1.5,
                          borderBottom: '1px solid',
                          borderColor: (t) => alpha(t.palette.primary.main, 0.1)
                        }
                      }}>
                        <TableHead>
                          <TableRow>
                            <TableCell>Switch</TableCell>
                            <TableCell>VLAN</TableCell>
                          </TableRow>
                        </TableHead>
                        <TableBody>
                          {((locStats.switchDetails && locStats.switchDetails.length > 0) ? locStats.switchDetails : (locStats.switches || [])).map((sw) => (
                            <TableRow key={sw.hostname} hover>
                              <TableCell sx={{ whiteSpace: 'nowrap' }}>
                                {/* Switch Hostname mit getrennten Klick-Bereichen wie in DataTable */}
                                {(() => {
                                  const hostname = String(sw.hostname || '');
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
                                              // SSH link functionality (no switch port copying for Statistics switches)
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

                                      {/* SSH Icon - click opens SSH, no switch port copy */}
                                      <Tooltip arrow placement="top" title={sshTitle}>
                                        <TerminalIcon
                                          className="ssh-icon"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            if (sshUsername && sshUsername.trim() !== '') {
                                              const sshUrl = `ssh://${sshUsername}@${hostname}`;
                                              toast.success(`🔗 SSH: ${sshUsername}@${hostname}`, { autoClose: 1000, pauseOnHover: false });
                                              setTimeout(() => { window.location.href = sshUrl; }, 150);
                                            } else {
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
                                              toast.warning(<ToastContent />, { autoClose: 6000, pauseOnHover: true, pauseOnFocusLoss: false });
                                            }
                                          }}
                                          sx={{
                                            color: (theme) => sshUsername
                                              ? (theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.6)' : '#4caf50')
                                              : (theme.palette.mode === 'dark' ? 'rgba(156, 163, 175, 0.6)' : '#9e9e9e'),
                                            fontSize: '14px',
                                            ml: 0.5,
                                            verticalAlign: 'middle',
                                            cursor: 'pointer'
                                          }}
                                        />
                                      </Tooltip>
                                    </Box>
                                  );
                                })()}
                              </TableCell>
                              <TableCell>
                                {/* Show VLANs for this specific switch */}
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

              <Accordion
                disableGutters
                elevation={0}
                TransitionProps={fastTransitionProps}
                sx={{
                  border: '1px solid',
                  borderColor: (t) => alpha(t.palette.success.main, 0.2),
                  borderRadius: 1,
                  '&:before': { display: 'none' },
                  backgroundColor: (t) => alpha(t.palette.success.light, t.palette.mode === 'dark' ? 0.04 : 0.03),
                  '& .MuiAccordionSummary-root': { transition: 'all 0.1s ease-in-out' },
                  '& .MuiAccordionDetails-root': { transition: 'all 0.1s ease-in-out' }
                }}
              >
                <AccordionSummary
                  expandIcon={<ExpandMoreIcon />}
                  sx={{ minHeight: '40px !important', '& .MuiAccordionSummary-content': { m: '8px 0 !important' } }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <ExtensionIcon sx={{ fontSize: '1.1rem', color: 'success.main' }} />
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'success.main' }}>
                        {(() => {
                          const q = String(locStats?.query || '').toUpperCase();
                          if (locStats?.mode === 'prefix' && q.length === 3 && cityNameByCode3[q]) {
                            return `Phones with KEM in ${cityNameByCode3[q]} (${q})`;
                          }
                          if (q && q.length === 5) {
                            const cityName = cityNameByCode3[q.slice(0, 3)] || '';
                            return `Phones with KEM in ${cityName ? `${q} (${cityName})` : q}`;
                          }
                          return 'Phones with KEM at this Location';
                        })()}
                      </Typography>
                    </Box>
                    <Chip
                      label={`${Number(locStats.phonesWithKEM || (locStats.kemPhones || []).length || 0).toLocaleString()} phones`}
                      size="small"
                      color="success"
                      variant="outlined"
                      sx={{
                        fontSize: '0.7rem',
                        height: '24px',
                        fontWeight: 600,
                        backgroundColor: (t) => alpha(t.palette.success.main, 0.08),
                        borderColor: (t) => t.palette.success.main,
                        color: (t) => t.palette.success.main
                      }}
                    />
                  </Box>
                </AccordionSummary>
                <AccordionDetails>
                  {locStatsLoading ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Skeleton key={i} variant="rectangular" height={24} />
                      ))}
                    </Box>
                  ) : (
                    <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 1, border: '1px solid', borderColor: (t) => alpha(t.palette.success.main, 0.1) }}>
                      <Table size="small" sx={{
                        '& .MuiTableCell-root': {
                          py: 0.8,
                          px: 1.5,
                          borderBottom: '1px solid',
                          borderColor: (t) => alpha(t.palette.success.main, 0.1)
                        }
                      }}>
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
                            // Handle both old format (CSV fields) and new format (backend objects)
                            const mac = p.mac || p['MAC Address'];
                            const ip = p.ip || p['IP Address'];
                            const model = p.model || p['Model Name'];
                            const serial = p.serial || p['Serial Number'];
                            const switchHostname = p.switch || p['Switch Hostname'];
                            // Ensure a unique, stable key (avoid collapsing duplicates visually)
                            const key = `${mac || 'nomac'}|${ip || 'noip'}|${serial || 'noserial'}|${switchHostname || 'nosw'}|${idx}`;
                            // Prefer kemModules when present; else derive from CSV fields with fallback to Line Number
                            const kemModulesVal = (typeof p.kemModules === 'number') ? p.kemModules
                              : (p.kemModules ? parseInt(String(p.kemModules), 10) : NaN);
                            let kemCount = Number.isFinite(kemModulesVal) ? kemModulesVal : undefined;
                            if (!Number.isFinite(kemCount)) {
                              const kem1 = (p['KEM'] || '').trim();
                              const kem2 = (p['KEM 2'] || '').trim();
                              const explicit = (kem1 ? 1 : 0) + (kem2 ? 1 : 0);
                              if (explicit > 0) {
                                kemCount = explicit;
                              } else {
                                const ln = (p['Line Number'] || '').trim();
                                kemCount = ln.includes('KEM') ? Math.max(1, (ln.match(/KEM/g) || []).length) : 1;
                              }
                            }
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
                                      href={`/search?q=${encodeURIComponent(mac)}`}
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
                                  {switchHostname ? (() => {
                                    const hostname = String(switchHostname || '');
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

                                        {/* SSH Icon - click opens SSH, no switch port copy */}
                                        <Tooltip arrow placement="top" title={sshTitle}>
                                          <TerminalIcon
                                            className="ssh-icon"
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              if (sshUsername && sshUsername.trim() !== '') {
                                                const sshUrl = `ssh://${sshUsername}@${hostname}`;
                                                toast.success(`🔗 SSH: ${sshUsername}@${hostname}`, { autoClose: 1000, pauseOnHover: false });
                                                setTimeout(() => { window.location.href = sshUrl; }, 150);
                                              } else {
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
                                                toast.warning(<ToastContent />, { autoClose: 6000, pauseOnHover: true, pauseOnFocusLoss: false });
                                              }
                                            }}
                                            sx={{
                                              color: (theme) => sshUsername
                                                ? (theme.palette.mode === 'dark' ? 'rgba(76, 175, 80, 0.6)' : '#4caf50')
                                                : (theme.palette.mode === 'dark' ? 'rgba(156, 163, 175, 0.6)' : '#9e9e9e'),
                                              fontSize: '14px',
                                              ml: 0.5,
                                              verticalAlign: 'middle',
                                              cursor: 'pointer'
                                            }}
                                          />
                                        </Tooltip>
                                      </Box>
                                    );
                                  })() : 'n/a'}
                                </TableCell>
                                <TableCell align="right">{Number(kemCount) || 0}</TableCell>
                              </TableRow>
                            );
                          })}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </AccordionDetails>
              </Accordion>

              {/* Location-specific timeline is collapsed by default and lazy-loads on expand */}
              {locSelected && (
                <Accordion
                  expanded={locTimelineExpanded}
                  onChange={(e, expanded) => setLocTimelineExpanded(expanded)}
                  TransitionProps={fastTransitionProps}
                  sx={{
                    border: '1px solid',
                    borderColor: (t) => alpha(t.palette.info.main, 0.2),
                    borderRadius: 1,
                    '&:before': { display: 'none' },
                    mt: 2,
                    backgroundColor: (t) => alpha(t.palette.info.light, t.palette.mode === 'dark' ? 0.04 : 0.03),
                  }}
                >
                  <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ minHeight: '40px !important', '& .MuiAccordionSummary-content': { m: '8px 0 !important' } }}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 700, color: 'text.secondary' }}>
                      Timeline for {(() => {
                        if (locStats?.mode === 'prefix' && locSelected?.length === 3 && cityNameByCode3[locSelected]) {
                          return `${cityNameByCode3[locSelected]} (${locSelected})`;
                        }
                        if (locSelected?.length === 5) {
                          const cityCode = locSelected.slice(0, 3);
                          const cityName = cityNameByCode3[cityCode];
                          return cityName ? `${locSelected} (${cityName})` : locSelected;
                        }
                        return locSelected;
                      })()} {locTimeline.series?.length ? `(${locTimeline.series.length} days)` : ''}
                    </Typography>
                  </AccordionSummary>
                  <AccordionDetails>
                    {/* KPI selector (shares state with global timeline; excludes Locations/Cities) */}
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Chip
                        label="Select All"
                        size="small"
                        color="success"
                        variant="filled"
                        onClick={selectAllLocKpis}
                        icon={<DoneAllIcon fontSize="small" />}
                        sx={{ fontWeight: 700 }}
                      />
                      <Chip
                        label="Clear"
                        size="small"
                        color="error"
                        variant="filled"
                        onClick={clearAllLocKpis}
                        icon={<ClearAllIcon fontSize="small" />}
                        sx={{ fontWeight: 700 }}
                      />
                      <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                      {KPI_DEFS_LOC.map((k) => {
                        const selected = selectedKpisLoc.includes(k.id);
                        return (
                          <Chip
                            key={k.id}
                            label={k.label}
                            size="small"
                            color="default"
                            variant={selected ? 'filled' : 'outlined'}
                            onClick={() => toggleKpiLoc(k.id)}
                            sx={selected ? { bgcolor: k.color, color: '#fff', '& .MuiChip-label': { fontWeight: 700 } } : undefined}
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
                        <LineChart
                          height={240}
                          xAxis={[{ data: (locTimeline.series || []).map((p) => (p.date ? String(p.date).slice(5) : p.file)), scaleType: 'point' }]}
                          series={selectedKpisLoc.length ? (
                            KPI_DEFS_LOC.filter(k => selectedKpisLoc.includes(k.id)).map((k) => ({
                              id: k.id,
                              label: k.label,
                              color: k.color,
                              data: (locTimeline.series || []).map((p) => p.metrics?.[k.id] || 0),
                            }))
                          ) : locEmptySeries}
                          margin={{ left: 52, right: 20, top: 56, bottom: 20 }}
                          yAxis={locYAxisBounds ? [{ min: locYAxisBounds.yMin, max: locYAxisBounds.yMax }] : undefined}
                          slotProps={{
                            legend: {
                              position: { vertical: 'top', horizontal: 'middle' },
                              direction: 'row',
                              itemGap: 16,
                            },
                          }}
                          sx={{ minWidth: 520 }}
                        />
                      </Box>
                    )}
                  </AccordionDetails>
                </Accordion>
              )}

              {/* Only summary metrics per location as requested */}
            </Paper>
          )}

          {isTimelines && (
            <>
              <Paper variant="outlined" sx={{ p: 2, mt: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.primary.main}`, backgroundColor: (t) => alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
                <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 700, color: 'primary.main' }}>
                  Global Timeline ({(timeline.series || []).length} days)
                </Typography>

                {/* Controls row: KPI chips left, days input right */}
                <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label="Select All"
                      size="small"
                      color="success"
                      variant="filled"
                      onClick={selectAllGlobalKpis}
                      icon={<DoneAllIcon fontSize="small" />}
                      sx={{ fontWeight: 700 }}
                    />
                    <Chip
                      label="Clear"
                      size="small"
                      color="error"
                      variant="filled"
                      onClick={clearAllGlobalKpis}
                      icon={<ClearAllIcon fontSize="small" />}
                      sx={{ fontWeight: 700 }}
                    />
                    <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                    {KPI_DEFS.map((k) => {
                      const selected = selectedKpisGlobal.includes(k.id);
                      return (
                        <Chip
                          key={k.id}
                          label={k.label}
                          size="small"
                          color="default"
                          variant={selected ? 'filled' : 'outlined'}
                          onClick={() => toggleKpiGlobal(k.id)}
                          sx={selected ? { bgcolor: k.color, color: '#fff', '& .MuiChip-label': { fontWeight: 700 } } : undefined}
                        />
                      );
                    })}
                  </Box>
                  <Box sx={{ ml: 'auto' }}>
                    <TextField
                      label="Days (0 = all)"
                      size="small"
                      type="number"
                      inputProps={{ min: 0 }}
                      value={timelineDays}
                      onChange={(e) => {
                        const v = Math.max(0, Number(e.target.value || 0));
                        setTimelineDays(v);
                      }}
                      sx={{ width: 160 }}
                    />
                  </Box>
                </Box>

                {timeline.loading ? (
                  <Skeleton variant="rectangular" height={240} />
                ) : timeline.error ? (
                  <Alert severity="info" variant="outlined">{timeline.error}</Alert>
                ) : (
                  <Box sx={{ width: '100%', overflowX: 'auto' }}>
                    <LineChart
                      height={260}
                      xAxis={[{ data: (timeline.series || []).map((p) => (p.date ? String(p.date).slice(5) : p.file)), scaleType: 'point' }]}
                      series={selectedKpisGlobal.length ? (
                        KPI_DEFS.filter(k => selectedKpisGlobal.includes(k.id)).map((k) => ({
                          id: k.id,
                          label: k.label,
                          color: k.color,
                          data: (timeline.series || []).map((p) => p.metrics?.[k.id] || 0),
                        }))
                      ) : globalEmptySeries}
                      margin={{ left: 52, right: 20, top: 56, bottom: 20 }}
                      yAxis={globalYAxisBounds ? [{ min: globalYAxisBounds.yMin, max: globalYAxisBounds.yMax }] : undefined}
                      slotProps={{
                        legend: {
                          position: { vertical: 'top', horizontal: 'middle' },
                          direction: 'row',
                          itemGap: 16,
                        },
                      }}
                      sx={{ minWidth: 520 }}
                    />
                  </Box>
                )}
              </Paper>

              {/* Top Locations Timeline */}
              <Paper variant="outlined" sx={{ p: 2, mt: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.secondary.main}`, backgroundColor: (t) => alpha(t.palette.secondary.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
                <Typography variant="subtitle1" sx={{ mb: 1.5, fontWeight: 700, color: 'secondary.main' }}>
                  Top 10 Locations Timeline ({(topTimeline.dates || []).length} days)
                </Typography>

                {/* Controls row: actions (locations) left, KPI next, days input right */}
                <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1, mb: 1 }}>
                  {/* Actions for locations selection */}
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 1 }}>
                    <Chip
                      label="Select All"
                      size="small"
                      color="success"
                      variant="filled"
                      onClick={selectAllTopKeys}
                      icon={<DoneAllIcon fontSize="small" />}
                      sx={{ fontWeight: 700 }}
                    />
                    <Chip
                      label="Clear"
                      size="small"
                      color="error"
                      variant="filled"
                      onClick={clearAllTopKeys}
                      icon={<ClearAllIcon fontSize="small" />}
                      sx={{ fontWeight: 700 }}
                    />
                    <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                  </Box>
                  {/* KPI */}
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                    {TOP_KPI_DEFS.map((k) => (
                      <Chip
                        key={k.id}
                        label={k.label}
                        size="small"
                        color="default"
                        variant={topKpi === k.id ? 'filled' : 'outlined'}
                        onClick={() => setTopKpi(k.id)}
                        sx={topKpi === k.id ? { bgcolor: k.color || '#1976d2', color: '#fff', '& .MuiChip-label': { fontWeight: 700 } } : undefined}
                      />
                    ))}
                  </Box>

                  {/* Count chips removed (fixed to Top 10) */}

                  {/* Days input (0 = all) */}
                  <Box sx={{ ml: 'auto' }}>
                    <TextField
                      label="Days (0 = all)"
                      size="small"
                      type="number"
                      inputProps={{ min: 0 }}
                      value={topDays}
                      onChange={(e) => {
                        const v = Math.max(0, Number(e.target.value || 0));
                        setTopDays(v);
                      }}
                      sx={{ width: 160 }}
                    />
                  </Box>
                </Box>

                {/* Keys selection (locations) */}
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
                  {sortedTopKeysForChips.map((k) => {
                    const selected = topSelectedKeys.includes(k);
                    const chipColor = topKeyColorMap[k];
                    return (
                      <Chip
                        key={`key-${k}`}
                        label={(topTimeline.labels && topTimeline.labels[k]) ? topTimeline.labels[k] : k}
                        size="small"
                        color="default"
                        variant={selected ? 'filled' : 'outlined'}
                        onClick={() => toggleTopKey(k)}
                        sx={selected ? { bgcolor: chipColor || 'secondary.main', color: '#fff', '& .MuiChip-label': { fontWeight: 700 } } : undefined}
                      />
                    );
                  })}
                </Box>

                {topTimeline.loading ? (
                  <Skeleton variant="rectangular" height={520} />
                ) : topTimeline.error ? (
                  <Alert severity="info" variant="outlined">{topTimeline.error}</Alert>
                ) : (
                  <Box sx={{ width: '100%', overflowX: 'auto' }}>
                    <LineChart
                      height={520}
                      xAxis={[{ data: (topTimeline.dates || []).map((d) => (d ? String(d).slice(5) : d)), scaleType: 'point' }]}
                      series={topSeriesPerKey.length ? topSeriesPerKey : topEmptySeries}
                      margin={{ left: 52, right: 20, top: 120, bottom: 28 }}
                      yAxis={topYAxisBounds ? [{ min: topYAxisBounds.yMin, max: topYAxisBounds.yMax, ticks: topYAxisBounds.ticks }] : undefined}
                      slotProps={{
                        legend: {
                          position: { vertical: 'top', horizontal: 'middle' },
                          direction: 'row',
                          itemGap: 20,
                        },
                      }}
                      sx={{ minWidth: 520 }}
                    />
                  </Box>
                )}
              </Paper>
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
});

export default StatisticsPage;
