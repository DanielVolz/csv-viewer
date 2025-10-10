import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

const CACHE_KEY = 'csvviewer_preview_cache';
const CACHE_DURATION_MS = 5 * 60 * 1000; // 5 minutes

/**
 * Custom hook for fetching a preview of the current CSV file from the backend API
 * Implements client-side caching to avoid redundant API calls
 * @param {Object} options - { enabled: boolean }
 * @returns {Object} { previewData, loading, error, refetch }
 */
function useFilePreview(options = {}) {
  const { enabled = true } = options;
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const mountedRef = useRef(true);
  const fetchingRef = useRef(false);

  // Try to load from cache first
  const loadFromCache = () => {
    try {
      const cached = sessionStorage.getItem(CACHE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        const age = Date.now() - timestamp;
        if (age < CACHE_DURATION_MS) {
          console.debug('[useFilePreview] Cache HIT (age:', Math.round(age / 1000), 's)');
          return data;
        } else {
          console.debug('[useFilePreview] Cache expired (age:', Math.round(age / 1000), 's)');
          sessionStorage.removeItem(CACHE_KEY);
        }
      }
    } catch (err) {
      console.debug('[useFilePreview] Cache read error:', err);
    }
    return null;
  };

  // Save to cache
  const saveToCache = (data) => {
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({
        data,
        timestamp: Date.now()
      }));
      console.debug('[useFilePreview] Cache saved');
    } catch (err) {
      console.debug('[useFilePreview] Cache write error:', err);
    }
  };

  const fetchPreview = useCallback(async (force = false) => {
    if (fetchingRef.current) {
      console.debug('[useFilePreview] Already fetching, skipping');
      return;
    }

    // Try cache first (unless forced)
    if (!force) {
      const cached = loadFromCache();
      if (cached) {
        setPreviewData(cached);
        setLoading(false);
        setError(null);
        return;
      }
    }

    const abortController = new AbortController();
    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      abortController.abort();
    }, 15000);

    try {
      fetchingRef.current = true;
      setLoading(true);
      console.debug('[useFilePreview] Fetching from API');

      // Single API call - backend preview includes all needed info
      const response = await axios.get('/api/files/preview', {
        params: { limit: 105 },
        signal: abortController.signal
      });

      if (!mountedRef.current) {
        fetchingRef.current = false;
        return;
      }

      const data = response.data;
      console.debug('[useFilePreview] API response:', {
        success: data?.success,
        rows: data?.data?.length || 0,
        file: data?.actual_file_name || data?.file_name
      });

      setPreviewData(data);
      setError(null);
      saveToCache(data);
    } catch (err) {
      if (!mountedRef.current) {
        fetchingRef.current = false;
        return;
      }

      if (axios.isCancel(err) || err?.name === 'CanceledError') {
        if (timedOut) {
          setError('Preview request timed out.');
          toast.error('Preview request timed out.', { autoClose: 4000 });
        } else {
          console.debug('[useFilePreview] Request cancelled (ignored)');
        }
      } else {
        console.error('[useFilePreview] Error:', err);
        const errorMessage = 'Failed to fetch file preview. Please try again later.';
        setError(errorMessage);
        toast.error(errorMessage, { position: 'top-right', autoClose: 5000 });
        setPreviewData({ success: false, message: 'Error connecting to backend', headers: [], data: [] });
      }
    } finally {
      clearTimeout(timeoutId);
      fetchingRef.current = false;
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    if (!enabled) {
      setLoading(false);
      setPreviewData(null);
      setError(null);
      return;
    }

    // Check cache IMMEDIATELY on mount (synchronously)
    const cached = loadFromCache();
    if (cached) {
      console.debug('[useFilePreview] Mount: Using cached data');
      setPreviewData(cached);
      setLoading(false);
      setError(null);
      return; // Don't fetch if cache is valid
    }

    // No cache - fetch from API
    console.debug('[useFilePreview] Mount: No cache, fetching from API');

    // Small delay to avoid double-fetch in StrictMode
    const timer = setTimeout(() => {
      if (mountedRef.current) {
        fetchPreview();
      }
    }, 10);

    return () => {
      clearTimeout(timer);
      mountedRef.current = false;
      fetchingRef.current = false;
    };
  }, [enabled, fetchPreview]);

  // Expose refetch function for manual refresh
  const refetch = () => {
    if (enabled) {
      sessionStorage.removeItem(CACHE_KEY); // Clear cache
      fetchPreview(true);
    }
  };

  return { previewData, loading, error, refetch };
}

// Export cache invalidation for external use (e.g., after file upload/change)
export const invalidatePreviewCache = () => {
  try {
    sessionStorage.removeItem(CACHE_KEY);
    console.debug('[useFilePreview] Cache invalidated externally');
  } catch (err) {
    console.debug('[useFilePreview] Cache invalidation error:', err);
  }
};

export default useFilePreview;
