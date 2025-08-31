import React from 'react';
import { Box, Card, CardContent, Grid, Typography, List, ListItem, ListItemText, Paper, Skeleton, Alert, Autocomplete, TextField, Chip, Accordion, AccordionSummary, AccordionDetails, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Tooltip, Button, Snackbar } from '@mui/material';
import { LineChart } from '@mui/x-charts';
import { alpha } from '@mui/material/styles';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CloseIcon from '@mui/icons-material/Close';
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

// Helper: determine if location is JVA (correctional facility) based on location code pattern
function isJVALocation(locationCode) {
  if (!locationCode) return false;
  const code = String(locationCode).trim();
  // JVA locations end with 50 or 51 (e.g., SRX50, SRX51)
  return /50$|51$/.test(code);
}

// Helper: determine if location is Justice institution
function isJusticeLocation(locationCode) {
  if (!locationCode) return false;
  // Justice locations are those that are not JVA
  return !isJVALocation(locationCode);
}

// Helper: extract city code from location code (e.g., MXX01 -> MXX, NXX02 -> NXX)
function extractCityCode(locationCode) {
  if (!locationCode) return 'Unknown';
  const code = String(locationCode).trim();
  // Extract first 3 characters as city code
  return code.substring(0, 3).toUpperCase();
}

// Helper: group locations by city and sort within each city by totalPhones
function groupLocationsByCity(locations) {
  if (!locations || locations.length === 0) return [];

  // Group by city code
  const groupedByCity = locations.reduce((acc, location) => {
    const cityCode = extractCityCode(location.location);
    if (!acc[cityCode]) {
      acc[cityCode] = [];
    }
    acc[cityCode].push(location);
    return acc;
  }, {});

  // Sort locations within each city by totalPhones (descending)
  Object.keys(groupedByCity).forEach(cityCode => {
    groupedByCity[cityCode].sort((a, b) => (b.totalPhones || 0) - (a.totalPhones || 0));
  });

  // Convert to array format and sort cities by total phones across all locations in city
  const cityGroups = Object.entries(groupedByCity).map(([cityCode, locations]) => {
    const totalCityPhones = locations.reduce((sum, loc) => sum + (loc.totalPhones || 0), 0);
    return {
      cityCode,
      cityName: locations[0]?.locationDisplay?.split(' - ')[1] || cityCode,
      locations,
      totalCityPhones
    };
  });

  // Sort cities by total phones (descending)
  cityGroups.sort((a, b) => b.totalCityPhones - a.totalCityPhones);

  return cityGroups;
}

// Icon mapping for different KPI types
const getKPIIcon = (title) => {
  const titleLower = title.toLowerCase();
  if (titleLower.includes('phone')) return PhoneIcon;
  if (titleLower.includes('switch')) return RouterIcon;
  if (titleLower.includes('location') && titleLower.includes('cities')) return LocationCityIcon;
  if (titleLower.includes('location')) return LocationOnIcon;
  if (titleLower.includes('kem')) return ExtensionIcon;
  if (titleLower.includes('cities')) return LocationCityIcon;
  return TrendingUpIcon; // default fallback
};

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
  const [allLocOptions, setAllLocOptions] = React.useState([]); // Cache all locations
  const [locError, setLocError] = React.useState(null);

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

  // Switch Port Cache für Statistics Switches
  const [switchPortCache, setSwitchPortCache] = React.useState({});

  // Location-specific timeline state
  const [locTimeline, setLocTimeline] = React.useState({ loading: false, error: null, series: [] });
  const locTimelineLoadedKeyRef = React.useRef('');

  // Local input state for immediate UI response, debounced for filtering
  const [localInput, setLocalInput] = React.useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('csv-viewer-settings') || '{}') || {};
      return saved.statistics?.lastSelectedLocation || '';
    } catch {
      return '';
    }
  });
  const [fieldFocused, setFieldFocused] = React.useState(false);
  const [isSearching, setIsSearching] = React.useState(false);
  const [selectedOptionIndex, setSelectedOptionIndex] = React.useState(-1); // For keyboard navigation

  // Simple handlers for the new TextField approach
  const handleLocationInputChange = React.useCallback((e) => {
    const val = e.target.value;
    setLocalInput(val); // Update local state immediately (no lag)
    setSelectedOptionIndex(-1); // Reset keyboard selection

    // Clear selection if input is empty
    if (!val || val.trim() === '') {
      setLocSelected(null);
      setIsSearching(false);

      // Immediately clear statistics when input is cleared
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
    } else if (val.length >= 2) {
      setIsSearching(true); // Start search indicator
    }
  }, []);

  // Debounce the actual locInput update for filtering (prevents lag)
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setLocInput(localInput);
      setIsSearching(false); // Search completed
    }, 300); // Increased to 300ms to reduce search frequency

    return () => clearTimeout(timer);
  }, [localInput]);

  // Reset selection when user starts typing (if input doesn't match selected location)
  React.useEffect(() => {
    if (locSelected && localInput) {
      const cityCode = locSelected.slice(0, 3);
      const cityName = cityNameByCode3[cityCode];
      const expectedDisplay = cityName ? `${locSelected} (${cityName})` : locSelected;

      // If user is typing something different than the expected display, clear selection
      if (localInput !== expectedDisplay && localInput !== locSelected) {
        setLocSelected(null);

        // Also clear stats when selection is cleared due to typing mismatch
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
    }
  }, [localInput, locSelected, cityNameByCode3]);

  // Save selected location to localStorage when it changes
  React.useEffect(() => {
    if (saveStatisticsPrefs) {
      saveStatisticsPrefs({ lastSelectedLocation: locSelected });
    }
  }, [locSelected, saveStatisticsPrefs]);

  // Update localInput display when city names are loaded or location changes
  React.useEffect(() => {
    if (locSelected && cityNameByCode3) {
      const cityCode = locSelected.slice(0, 3);
      const cityName = cityNameByCode3[cityCode];
      const displayValue = cityName ? `${locSelected} (${cityName})` : locSelected;

      // Only update if current localInput doesn't already match the expected display
      if (localInput !== displayValue) {
        setLocalInput(displayValue);
      }
    }
  }, [locSelected, cityNameByCode3, localInput]);

  const handleLocationFocus = React.useCallback(() => {
    setFieldFocused(true);
    setSelectedOptionIndex(-1); // Reset keyboard selection when focusing
  }, []);

  const handleLocationBlur = React.useCallback((e) => {
    // Delay hiding dropdown to allow clicking on options
    setTimeout(() => setFieldFocused(false), 150);

    const val = (e.target.value || '').trim().toUpperCase();
    if (val && /^[A-Z]{3}[0-9]{2}$/.test(val) && (!Array.isArray(locOptions) || !locOptions.includes(val))) {
      // Valid format but location doesn't exist
      setSnackbar({
        open: true,
        message: `Location "${val}" does not exist. Please select from available locations.`
      });
      // Clear the input field
      setLocInput('');
    }
  }, [locOptions]);

  const handleLocationKeyDown = React.useCallback((e) => {
    const visibleOptions = locOptions.slice(0, 50);
    const hasCityHint = localInput.length === 3 && locOptions.length > 0 && cityNameByCode3[localInput.toUpperCase()];
    const totalOptions = hasCityHint ? visibleOptions.length + 1 : visibleOptions.length; // +1 for city hint

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedOptionIndex(prev => {
        const next = prev < totalOptions - 1 ? prev + 1 : 0;
        return next;
      });
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedOptionIndex(prev => {
        const next = prev > 0 ? prev - 1 : totalOptions - 1;
        return next;
      });
    } else if (e.key === 'Enter') {
      e.preventDefault();

      if (selectedOptionIndex >= 0 && selectedOptionIndex < totalOptions) {
        if (hasCityHint && selectedOptionIndex === 0) {
          // Select city search (first option)
          const cityCode = localInput.toUpperCase();
          const cityName = cityNameByCode3[cityCode];
          setLocSelected(cityCode);
          setLocalInput(`${cityCode} (${cityName})`);
          setLocInput(cityCode);
          setFieldFocused(false);
          setSelectedOptionIndex(-1);
        } else {
          // Select specific location option
          const optionIndex = hasCityHint ? selectedOptionIndex - 1 : selectedOptionIndex;
          if (optionIndex >= 0 && optionIndex < visibleOptions.length) {
            const selectedOption = visibleOptions[optionIndex];
            const cityCode = selectedOption.slice(0, 3);
            const cityName = cityNameByCode3[cityCode];
            const displayValue = cityName ? `${selectedOption} (${cityName})` : selectedOption;

            setLocSelected(selectedOption);
            setLocalInput(displayValue);
            setLocInput(selectedOption);
            setFieldFocused(false);
            setSelectedOptionIndex(-1);
          }
        }
      } else {
        // Fallback to original logic
        const val = (e.target.value || '').trim();
        const upperVal = val.toUpperCase();
        if (Array.isArray(locOptions) && locOptions.includes(upperVal)) {
          const cityCode = upperVal.slice(0, 3);
          const cityName = cityNameByCode3[cityCode];
          const displayValue = cityName ? `${upperVal} (${cityName})` : upperVal;

          setLocSelected(upperVal);
          setLocalInput(displayValue);
          setLocInput(upperVal);
        } else if (upperVal && /^[A-Z]{3}[0-9]{2}$/.test(upperVal)) {
          setSnackbar({
            open: true,
            message: `Location "${upperVal}" does not exist. Please select from available locations.`
          });
          setLocalInput('');
          setLocInput('');
        }
      }

      if (e.target && typeof e.target.blur === 'function') {
        e.target.blur();
      }
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setFieldFocused(false);
      setSelectedOptionIndex(-1);
      if (e.target && typeof e.target.blur === 'function') {
        e.target.blur();
      }
    }
  }, [locOptions, selectedOptionIndex, cityNameByCode3, localInput]);

  // Helper function to select a location and show formatted value in input
  const selectLocation = React.useCallback((option) => {
    const cityCode = option.slice(0, 3);
    const cityName = cityNameByCode3[cityCode];
    const displayValue = cityName ? `${option} (${cityName})` : option;

    setLocSelected(option);
    setLocalInput(displayValue); // Show formatted value in input
    setLocInput(option); // But use raw location code for API
    setFieldFocused(false);
    setSelectedOptionIndex(-1);
  }, [cityNameByCode3]);

  const handleCityNameChange = React.useCallback((_, value) => {
    if (value) {
      // Find location code for this city name
      const cityCode = Object.entries(cityNameByCode3).find(([code, name]) =>
        name.toLowerCase() === value.toLowerCase()
      )?.[0];

      if (cityCode) {
        setLocSelected(cityCode);
        setLocalInput(`${cityCode} (${value})`); // Show city name in input
        setLocInput(cityCode);
      }
    }
  }, [cityNameByCode3]);

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

  // Load ALL locations once at startup
  React.useEffect(() => {
    let abort = false;
    const controller = new AbortController();

    (async () => {
      try {
        setLocError(null);
        // Use FAST OpenSearch-based API - now working!
        const r = await fetch(`/api/stats/fast/locations?limit=1000`, { signal: controller.signal });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (abort) return;
        const options = (json?.options || []).filter((o) => /^[A-Z]{3}[0-9]{2}$/.test(String(o)));
        setAllLocOptions(options);
        setLocOptions(options.slice(0, 50)); // Show first 50 initially (more results)
      } catch (e) {
        if (e.name === 'AbortError') return;
        setLocError('Failed to load locations');
      }
    })();

    return () => { abort = true; controller.abort(); };
  }, []); // Only run once on mount

  // Fast local filtering of cached locations (NO DEBOUNCING since localInput is already debounced)
  React.useEffect(() => {
    if (!allLocOptions.length) return;

    // No additional debouncing needed since localInput -> locInput is already debounced
    const input = locInput.trim().toUpperCase();
    if (!input) {
      setLocOptions(allLocOptions.slice(0, 50)); // Show more results when empty
      return;
    }

    // Start filtering at 2 characters (e.g., "MX" to show "MXX09", "MXX17")
    if (input.length < 2) {
      setLocOptions([]);
      return;
    }

    // Optimized filtering with prioritized results (exact matches first)
    const exactMatches = [];
    const startsWithMatches = [];
    const containsMatches = [];

    for (let i = 0; i < allLocOptions.length; i++) {
      const option = allLocOptions[i].toUpperCase();
      if (option === input) {
        exactMatches.push(allLocOptions[i]);
      } else if (option.startsWith(input)) {
        startsWithMatches.push(allLocOptions[i]);
      } else if (option.includes(input)) {
        containsMatches.push(allLocOptions[i]);
      }

      // Limit total results for performance
      if (exactMatches.length + startsWithMatches.length + containsMatches.length >= 100) {
        break;
      }
    }

    // Combine results with priority: exact > starts with > contains
    const filtered = [...exactMatches, ...startsWithMatches, ...containsMatches].slice(0, 100);
    setLocOptions(filtered);
  }, [locInput, allLocOptions]);

  // Debounce locSelected changes to prevent API spam while typing
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedLocSelected(locSelected);
    }, 500); // 500ms delay after selection stops changing

    return () => clearTimeout(timer);
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

  // Fetch per-location timeline whenever the selected location changes
  React.useEffect(() => {
    if (!debouncedLocSelected) {
      // Reset timeline when no location is selected
      setLocTimeline({ loading: false, error: null, series: [] });
      locTimelineLoadedKeyRef.current = '';
      return;
    }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedLocSelected]);

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
        <Typography variant="subtitle1" sx={{ mb: 3, fontWeight: 600 }}>General Statistics</Typography>

        {/* Total Section */}
        <Box sx={{
          mb: 3,
          p: 2,
          borderRadius: 2,
          backgroundColor: (theme) => alpha(theme.palette.primary.main, theme.palette.mode === 'dark' ? 0.08 : 0.06),
          border: '1px solid',
          borderColor: (theme) => alpha(theme.palette.primary.main, 0.2)
        }}>
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600, color: 'primary.main', display: 'flex', alignItems: 'center', gap: 1 }}>
            <PublicIcon sx={{ fontSize: '1.3rem' }} />
            Total Phones
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Phones" value={data.totalPhones} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Switches" value={data.totalSwitches} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Total Locations" value={data.totalLocations} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Total Cities" value={data.totalCities} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={data.phonesWithKEM} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Total KEMs" value={data.totalKEMs} loading={loading} /></Grid>
          </Grid>
        </Box>

        {/* Justice Section */}
        <Box sx={{
          mb: 3,
          p: 2,
          borderRadius: 2,
          backgroundColor: justiceTheme.background,
          border: '1px solid',
          borderColor: justiceTheme.border
        }}>
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600, color: justiceTheme.primary, display: 'flex', alignItems: 'center', gap: 1 }}>
            <GavelIcon sx={{ fontSize: '1.3rem' }} />
            Justice Institutions (Justiz)
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Phones" value={data.totalJustizPhones} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Switches" value={data.justizSwitches} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Locations" value={data.justizLocations} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Cities" value={data.justizCities} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={data.justizPhonesWithKEM} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Total KEMs" value={data.totalJustizKEMs} loading={loading} /></Grid>
          </Grid>
        </Box>

        {/* JVA Section */}
        <Box sx={{
          p: 2,
          borderRadius: 2,
          backgroundColor: jvaTheme.background,
          border: '1px solid',
          borderColor: jvaTheme.border
        }}>
          <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600, color: jvaTheme.primary, display: 'flex', alignItems: 'center', gap: 1 }}>
            <SecurityIcon sx={{ fontSize: '1.3rem' }} />
            Correctional Facilities (JVA)
          </Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Phones" value={data.totalJVAPhones} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Switches" value={data.jvaSwitches} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Locations" value={data.jvaLocations} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="warning" title="Cities" value={data.jvaCities} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={data.jvaPhonesWithKEM} loading={loading} /></Grid>
            <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Total KEMs" value={data.totalJVAKEMs} loading={loading} /></Grid>
          </Grid>
        </Box>
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
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', mr: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <PlaceIcon sx={{ fontSize: '1.1rem', color: 'info.main' }} />
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                              View by Location ({(data.phonesByModelJustizDetails || []).length} locations)
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={(e) => { e.stopPropagation(); expandAllJustizCities(); }}
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
                              onClick={(e) => { e.stopPropagation(); collapseAllJustizCities(); }}
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
                        </Box>
                      </AccordionSummary>
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
                                              {location.location}
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
                                                  key={`${location.location}-${modelData.model}`}
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
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', mr: 1 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <PlaceIcon sx={{ fontSize: '1.1rem', color: 'warning.main' }} />
                            <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600 }}>
                              View by Location ({(data.phonesByModelJVADetails || []).length} locations)
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', gap: 1 }}>
                            <Button
                              size="small"
                              variant="outlined"
                              onClick={(e) => { e.stopPropagation(); expandAllJvaCities(); }}
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
                              onClick={(e) => { e.stopPropagation(); collapseAllJvaCities(); }}
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
                        </Box>
                      </AccordionSummary>
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
                                              {location.location}
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
                                                  key={`${location.location}-${modelData.model}`}
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

      {/* Statistics by Location */}
      <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, borderTop: (t) => `4px solid ${t.palette.info.main}`, backgroundColor: (t) => alpha(t.palette.info.light, t.palette.mode === 'dark' ? 0.08 : 0.05) }}>
        <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 700, color: 'info.main' }}>Statistics by Location</Typography>

        {/* Two search fields side by side */}
        <Grid container spacing={2} sx={{ mb: 2 }}>
          {/* Location Code Search - Simplified for Performance */}
          <Grid item xs={12} md={6}>
            <Box sx={{ position: 'relative' }}>
              <TextField
                label="Search by Location Code"
                placeholder="Type 2+ letters (MX) or full code (MXX09)"
                size="small"
                fullWidth
                value={localInput}
                onChange={handleLocationInputChange}
                onFocus={handleLocationFocus}
                onBlur={handleLocationBlur}
                onKeyDown={handleLocationKeyDown}
                helperText={
                  isSearching && localInput.length >= 2
                    ? "Searching..."
                    : localInput.length > 0 && localInput.length < 2
                      ? "Type at least 2 characters to search"
                      : localInput.length >= 2 && allLocOptions.length > 0 && locOptions.length === 0 && !locSelected
                        ? "No matching locations found"
                        : ""
                }
                InputProps={{
                  endAdornment: locSelected && (
                    <CloseIcon
                      fontSize="small"
                      onClick={() => {
                        // Immediate clear - no delays
                        setLocSelected(null);
                        setLocalInput('');
                        setLocInput('');
                        setSelectedOptionIndex(-1);

                        // Immediately clear statistics data to avoid delay
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

                        // Clear from localStorage as well
                        if (saveStatisticsPrefs) {
                          saveStatisticsPrefs({ lastSelectedLocation: null });
                        }
                      }}
                      sx={{
                        cursor: 'pointer',
                        '&:hover': { color: 'primary.main' }
                      }}
                    />
                  ),
                }}
              />

              {/* Modern dropdown list with improved design */}
              {fieldFocused && locOptions.length > 0 && (
                <Paper
                  sx={{
                    position: 'absolute',
                    top: '100%',
                    left: 0,
                    right: 0,
                    zIndex: 1300,
                    maxHeight: 320,
                    overflow: 'hidden',
                    mt: 0.5,
                    borderRadius: 2,
                    border: 1,
                    borderColor: 'primary.main',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.12)',
                  }}
                  elevation={0}
                >
                  <Box sx={{ maxHeight: 320, overflowY: 'auto' }}>
                    {/* Show hint for 3-letter city codes as first item */}
                    {localInput.length === 3 && locOptions.length > 0 && (() => {
                      const cityCode = localInput.toUpperCase();
                      const cityName = cityNameByCode3[cityCode];
                      const isSelected = selectedOptionIndex === 0;

                      if (cityName) {
                        return (
                          <Box
                            onClick={() => {
                              // Search by city prefix (all locations starting with this code)
                              setLocSelected(cityCode);
                              setLocalInput(`${cityCode} (${cityName})`);
                              setLocInput(cityCode);
                              setFieldFocused(false);
                              setSelectedOptionIndex(-1);
                            }}
                            sx={{
                              px: 2,
                              py: 1.5,
                              backgroundColor: isSelected ? 'primary.dark' : 'primary.main',
                              color: 'primary.contrastText',
                              borderBottom: 1,
                              borderColor: 'divider',
                              cursor: 'pointer',
                              borderLeft: isSelected ? 4 : 0,
                              borderLeftColor: 'primary.contrastText',
                              '&:hover': {
                                backgroundColor: 'primary.dark'
                              },
                              transition: 'all 0.2s ease'
                            }}
                          >
                            <Typography variant="body2" sx={{ fontWeight: 500 }}>
                              🔍 Search all locations in {cityName}
                            </Typography>
                          </Box>
                        );
                      }
                      return null;
                    })()}

                    {locOptions.slice(0, 50).map((option, index) => {
                      const cityCode = option.slice(0, 3);
                      const cityName = cityNameByCode3[cityCode];
                      const hasCityHint = localInput.length === 3 && cityNameByCode3[localInput.toUpperCase()];
                      const adjustedIndex = hasCityHint ? index + 1 : index; // Adjust for city hint
                      const isSelected = adjustedIndex === selectedOptionIndex;

                      return (
                        <Box
                          key={option}
                          onClick={() => selectLocation(option)}
                          sx={{
                            px: 2,
                            py: 1.5,
                            cursor: 'pointer',
                            backgroundColor: isSelected ? 'primary.light' : 'transparent',
                            borderLeft: isSelected ? 4 : 0,
                            borderLeftColor: 'primary.main',
                            '&:hover': {
                              backgroundColor: isSelected ? 'primary.light' : 'action.hover',
                              borderLeft: 4,
                              borderLeftColor: 'primary.main'
                            },
                            '&:not(:last-child)': {
                              borderBottom: 1,
                              borderColor: 'divider'
                            },
                            transition: 'all 0.2s ease'
                          }}
                        >
                          <Typography
                            variant="body1"
                            sx={{
                              fontWeight: 600,
                              color: isSelected ? 'primary.main' : 'text.primary'
                            }}
                          >
                            {option}
                          </Typography>
                          {cityName && (
                            <Typography
                              variant="body2"
                              sx={{
                                color: isSelected ? 'primary.dark' : 'text.secondary',
                                mt: 0.25
                              }}
                            >
                              📍 {cityName}
                            </Typography>
                          )}
                        </Box>
                      );
                    })}
                  </Box>
                </Paper>
              )}
            </Box>
          </Grid>

          {/* City Name Search */}
          <Grid item xs={12} md={6}>
            <Autocomplete
              options={Object.values(cityNameByCode3).sort()}
              freeSolo={false} // Change to false for better performance
              openOnFocus={false} // Disable auto-open for performance
              // Keep popup size fixed and make options scrollable
              slotProps={{
                paper: { sx: { maxHeight: 200, overflowY: 'auto' } }, // Reduced height
                listbox: { sx: { maxHeight: 160, overflowY: 'auto' } },
              }}
              ListboxProps={{
                style: { maxHeight: 160, overflowY: 'auto' },
              }}
              limitTags={5}
              disableListWrap={true}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label="Search by City Name"
                  placeholder="Type city name (e.g., München, Augsburg)"
                  size="small"
                />
              )}
              onChange={handleCityNameChange}
              filterOptions={filterCityOptions}
              getOptionLabel={(option) => option}
              renderOption={(props, option) => {
                // Find the corresponding location code
                const cityCode = Object.entries(cityNameByCode3).find(([code, name]) =>
                  name === option
                )?.[0];

                // Extract key from props to avoid React warning
                const { key, ...otherProps } = props;

                return (
                  <li key={key} {...otherProps}>
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
            <Alert severity="warning" variant="outlined">{locError}</Alert>
          </Box>
        )}

        <Grid container spacing={2} sx={{ mb: 1 }}>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="primary" title="Total Phones" value={locStats.totalPhones} loading={locStatsLoading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="info" title="Total Switches" value={locStats.totalSwitches} loading={locStatsLoading} /></Grid>
          <Grid item xs={12} sm={6} md={3}><StatCard tone="success" title="Phones with KEM" value={locStats.phonesWithKEM} loading={locStatsLoading} /></Grid>
        </Grid>

        {locStats?.mode === 'prefix' && locStats?.query && (
          <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
            <Typography variant="body2" sx={{ fontWeight: 600 }}>
              City-wide Statistics for {cityNameByCode3[locStats.query] || locStats.query}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Showing aggregated data across all locations starting with {locStats.query} (e.g., {locStats.query}01, {locStats.query}02, {locStats.query}03, ...)
            </Typography>
          </Alert>
        )}

        {/* Location-specific timeline (last 31 days) */}
        {locSelected && (
          <Box sx={{ mt: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 700, color: 'text.secondary' }}>
              Timeline for {(() => {
                // If it's a 3-letter code and we have city data in prefix mode, show city name
                if (locStats?.mode === 'prefix' && locSelected?.length === 3 && cityNameByCode3[locSelected]) {
                  return `${cityNameByCode3[locSelected]} (${locSelected})`;
                }
                // If it's a 5-letter location code, show with city name
                if (locSelected?.length === 5) {
                  const cityCode = locSelected.slice(0, 3);
                  const cityName = cityNameByCode3[cityCode];
                  return cityName ? `${locSelected} (${cityName})` : locSelected;
                }
                // Otherwise just show the location code
                return locSelected;
              })()} ({(locTimeline.series || []).length} days)
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
                  {/* Show both sections for city search (3-letter codes), or specific section for exact locations, but only if data exists */}
                  {(!locSelected || locSelected.length === 3 || isJusticeLocation(locSelected)) &&
                    (locStats.phonesByModelJustiz || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length > 0 && (
                      <Box sx={{
                        mb: 2,
                        p: 1.5,
                        borderRadius: 1,
                        backgroundColor: justiceTheme.background,
                        border: '1px solid',
                        borderColor: justiceTheme.border
                      }}>
                        <Typography variant="body2" sx={{ fontWeight: 600, color: justiceTheme.primary, mb: 0.5 }}>
                          Justice institutions (Justiz)
                        </Typography>
                        <List dense sx={{ mb: 0 }}>
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
                        </List>
                      </Box>
                    )}

                  {(!locSelected || locSelected.length === 3 || isJVALocation(locSelected)) &&
                    (locStats.phonesByModelJVA || []).filter(({ model }) => model && model !== 'Unknown' && !isMacLike(model)).length > 0 && (
                      <Box sx={{
                        mb: 2,
                        p: 1.5,
                        borderRadius: 1,
                        backgroundColor: jvaTheme.background,
                        border: '1px solid',
                        borderColor: jvaTheme.border
                      }}>
                        <Typography variant="body2" sx={{ fontWeight: 600, color: jvaTheme.primary, mb: 0.5 }}>
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
                        </List>
                      </Box>
                    )}
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
          <Accordion
            disableGutters
            elevation={0}
            TransitionProps={fastTransitionProps}
            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' }, mt: 2, mb: 1, backgroundColor: (t) => alpha(t.palette.primary.light, t.palette.mode === 'dark' ? 0.04 : 0.03) }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="body2" fontWeight={700} color="primary.main">
                Switches {(() => {
                  if (locStats?.mode === 'prefix' && cityNameByCode3[locStats?.query]) {
                    return `in ${cityNameByCode3[locStats.query]} (${locStats.query})`;
                  }
                  return 'at this Location';
                })()} ({locStats.totalSwitches?.toLocaleString?.() ?? locStats.totalSwitches})
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
            sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 1, '&:before': { display: 'none' }, backgroundColor: (t) => alpha(t.palette.success.light, t.palette.mode === 'dark' ? 0.04 : 0.03) }}
          >
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
                        // Handle both old format (CSV fields) and new format (backend objects)
                        const key = (p.mac || p['MAC Address'] || p.ip || p['IP Address'] || String(idx));
                        const mac = p.mac || p['MAC Address'];
                        const ip = p.ip || p['IP Address'];
                        const model = p.model || p['Model Name'];
                        const serial = p.serial || p['Serial Number'];
                        const switchHostname = p.switch || p['Switch Hostname'];
                        // For new format, assume 1 KEM (since they are in kemPhones array)
                        const kem1 = p['KEM'] ? (p['KEM'] || '').trim() : 'KEM';
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

      {/* Snackbar for location validation feedback */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleSnackbarClose}
        message={snackbar.message}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      />
    </Box>
  );
});

export default StatisticsPage;
