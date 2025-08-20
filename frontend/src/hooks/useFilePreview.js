import { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

/**
 * Custom hook for fetching a preview of the current CSV file from the backend API
 * @param {number} limit - Maximum number of entries to fetch
 * @returns {Object} { previewData, loading, error }
 */
function useFilePreview() { // Removed limit parameter to prevent re-renders
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const abortController = new AbortController();
    const timeoutRef = { current: null };
    let timedOut = false;
    let mounted = true;
    console.debug('[useFilePreview] effect start');

    const fetchPreview = async () => {
      try {
        setLoading(true);
        console.debug('[useFilePreview] fetchPreview START');
        // Safety timeout (15s)
        timeoutRef.current = setTimeout(() => {
          if (!timedOut && mounted) {
            timedOut = true;
            abortController.abort();
          }
        }, 15000);

        const infoResponse = await axios.get('/api/files/netspeed_info', { signal: abortController.signal });
        console.debug('[useFilePreview] netspeed_info response', infoResponse.data);
        const fileInfo = infoResponse.data;

        const response = await axios.get('/api/files/preview', {
          params: { limit: 105 },
          signal: abortController.signal
        });
        console.debug('[useFilePreview] preview response meta', {
          success: response.data?.success,
          message: response.data?.message,
          headersLen: Array.isArray(response.data?.headers) ? response.data.headers.length : null,
          rows: Array.isArray(response.data?.data) ? response.data.data.length : null
        });

        // Get the original data
        const originalData = response.data;

        // Use headers and data as provided by backend (backend controls what's displayed)
        const nextData = {
          ...originalData,
          line_count: fileInfo.line_count || 0
        };
        console.debug('[useFilePreview] setPreviewData', nextData);
        setPreviewData(nextData);

        setError(null);
      } catch (err) {
        if (!mounted) return; // Ignore after unmount
        if (axios.isCancel(err) || err?.name === 'CanceledError') {
          // Distinguish between deliberate timeout and React StrictMode double-invoke abort
          if (timedOut) {
            setError('Preview request timed out.');
            toast.error('Preview request timed out.', { autoClose: 4000 });
          } else {
            // Silent cancellation (StrictMode/unmount) — no UI noise
            console.debug('Preview request cancelled (ignored).');
          }
        } else {
          console.error('Error fetching file preview:', err);
          const errorMessage = 'Failed to fetch file preview. Please try again later.';
          setError(errorMessage);
          toast.error(errorMessage, { position: 'top-right', autoClose: 5000 });
          setPreviewData({ success: false, message: 'Error connecting to backend', headers: [], data: [] });
        }
      } finally {
        if (mounted) {
          clearTimeout(timeoutRef.current);
          setLoading(false);
          // Avoid capturing previewData here to keep deps stable
          console.debug('[useFilePreview] fetchPreview END', { timedOut });
        }
      }
    };

    fetchPreview();
    return () => {
      mounted = false;
      clearTimeout(timeoutRef.current);
      abortController.abort();
      console.debug('[useFilePreview] cleanup');
    };
  }, []);

  return { previewData, loading, error };
}

export default useFilePreview;
