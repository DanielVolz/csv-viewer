import { useCallback, useMemo, useRef, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useSearchContext } from '../contexts/SearchContext';

/**
 * Custom hook for searching CSV files in the backend API
 * @returns {Object} { searchAll, results, loading, error, pagination }
 */
function useSearchCSV() {
  const {
    rawResults,
    setRawResults,
    pagination,
    setPaginationState,
    loading,
    setLoading,
    error,
    setError,
    setLastQuery
  } = useSearchContext();

  // Use ref to stabilize the search function reference
  const searchAllRef = useRef();
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  // The actual search function implementation
  const searchAllImpl = useCallback(async (searchTerm, includeHistorical = true, showToasts = true) => {
    if (!searchTerm) {
      const errorMessage = 'Please enter a search term';
      if (mountedRef.current) setError(errorMessage);
      if (showToasts) {
        toast.warning(errorMessage);
      }
      return false;
    }

    try {
      if (mountedRef.current) {
        setLoading(true);
        setError(null);
      }

      const response = await axios.get('/api/search/', {
        params: {
          query: searchTerm,
          field: null,
          include_historical: includeHistorical
        },
        timeout: 30000
      });

      const originalData = response.data;

      if (!mountedRef.current) {
        return true;
      }

      setRawResults(originalData);
      setLastQuery(searchTerm);

      const totalItems = Array.isArray(originalData?.data) ? originalData.data.length : 0;

      if (showToasts) {
        if (originalData.success && totalItems === 0) {
          toast.info('No results found for your search term.', {
            position: 'top-right',
            autoClose: 3000
          });
        } else if (totalItems > 0) {
          toast.success(`Found ${totalItems} results for "${searchTerm}"`, {
            position: 'top-right',
            autoClose: 3000
          });
        }
      }

      setPaginationState((prev) => {
        const pageSize = prev.pageSize || 100;
        const totalPages = pageSize > 0 ? Math.ceil(totalItems / pageSize) : 0;
        const currentPage = prev.page || 1;
        const nextPage = totalPages > 0 ? Math.min(currentPage, totalPages) : 1;
        return {
          ...prev,
          totalItems,
          totalPages,
          page: nextPage
        };
      });

      return true;
    } catch (err) {
      console.error('Error searching term:', err);

      if (!mountedRef.current) {
        return false;
      }

      let errorMessage = '';
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Search timed out. Please try a more specific search term.';
      } else if (err.response && err.response.status === 504) {
        errorMessage = 'Search timed out on the server. Please try a more specific search term.';
      } else {
        errorMessage = 'Failed to search. Please try again later.';
      }

      setError(errorMessage);
      if (showToasts) {
        toast.error(errorMessage);
      }

      setRawResults(null);
      setPaginationState((prev) => ({
        ...prev,
        totalItems: 0,
        totalPages: 0,
        page: 1
      }));

      return false;
    } finally {
      if (mountedRef.current) {
        setLoading(false);
      }
    }
  }, [setError, setLoading, setRawResults, setPaginationState, setLastQuery]);

  // Assign the implementation to the ref
  searchAllRef.current = searchAllImpl;

  // Create a stable reference to the search function
  const searchAll = useCallback((...args) => {
    return searchAllRef.current(...args);
  }, []);

  const setPage = useCallback((page) => {
    setPaginationState((prev) => {
      const pageSize = prev.pageSize || 100;
      const knownTotalPages = prev.totalPages || 0;
      const fallbackTotalPages = pageSize > 0 && Array.isArray(rawResults?.data)
        ? Math.ceil(rawResults.data.length / pageSize)
        : 0;
      const totalPages = knownTotalPages > 0 ? knownTotalPages : fallbackTotalPages;
      const safeTotalPages = totalPages > 0 ? totalPages : 1;
      const nextPage = Math.max(1, Math.min(page, safeTotalPages));
      return {
        ...prev,
        page: nextPage
      };
    });
  }, [setPaginationState, rawResults]);

  const setPageSize = useCallback((size) => {
    const newSize = Math.max(10, Math.min(size, 500));

    setPaginationState((prev) => {
      const totalItems = typeof prev.totalItems === 'number'
        ? prev.totalItems
        : (Array.isArray(rawResults?.data) ? rawResults.data.length : 0);
      const totalPages = newSize > 0 ? Math.ceil(totalItems / newSize) : 0;
      const currentPage = prev.page || 1;
      const nextPage = totalPages > 0 ? Math.min(currentPage, totalPages) : 1;
      return {
        ...prev,
        pageSize: newSize,
        totalItems,
        totalPages,
        page: nextPage
      };
    });
  }, [setPaginationState, rawResults]);

  // Get the current page of results - memoized to prevent re-renders
  const paginatedResults = useMemo(() => {
    if (!rawResults || !Array.isArray(rawResults.data)) {
      return rawResults;
    }

    const pageSize = pagination?.pageSize || 100;
    const totalItems = typeof pagination?.totalItems === 'number'
      ? pagination.totalItems
      : rawResults.data.length;
    const inferredTotalPages = pageSize > 0 ? Math.ceil(totalItems / pageSize) : 0;
    const totalPages = typeof pagination?.totalPages === 'number'
      ? pagination.totalPages
      : inferredTotalPages;
    const safeTotalPages = totalPages > 0 ? totalPages : 1;
    const currentPage = Math.max(1, Math.min(pagination?.page || 1, safeTotalPages));
    const start = (currentPage - 1) * pageSize;
    const end = start + pageSize;

    return {
      ...rawResults,
      data: rawResults.data.slice(start, end),
      pagination: {
        page: currentPage,
        pageSize,
        totalItems,
        totalPages,
        currentStart: start + 1,
        currentEnd: Math.min(end, totalItems)
      }
    };
  }, [rawResults, pagination]);

  return {
    searchAll,
    results: paginatedResults,
    allResults: rawResults,
    loading,
    error,
    pagination,
    setPage,
    setPageSize
  };
}

export default useSearchCSV;
