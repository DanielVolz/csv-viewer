import { useState, useCallback, useMemo, useRef } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

/**
 * Custom hook for searching CSV files in the backend API
 * @returns {Object} { searchAll, results, loading, error, pagination }
 */
function useSearchCSV() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 100,
    totalItems: 0,
    totalPages: 0
  });

  // Use ref to stabilize the search function reference
  const searchAllRef = useRef();

  // The actual search function implementation
  const searchAllImpl = useCallback(async (searchTerm, includeHistorical = true, showToasts = true) => {
    if (!searchTerm) {
      const errorMessage = 'Please enter a search term';
      setError(errorMessage);
      if (showToasts) {
        toast.warning(errorMessage);
      }
      return false;
    }

    try {
      setLoading(true);
      setError(null);

      // The actual API call happens regardless of showToasts
      const response = await axios.get('/api/search/', {
        params: {
          query: searchTerm,
          field: null, // Always search in all fields
          include_historical: includeHistorical
        },
        timeout: 30000 // 30 second timeout
      });

      // Get the original data
      const originalData = response.data;

      // Use data as provided by backend (backend controls what's displayed)
      if (originalData.success && Array.isArray(originalData.data) && originalData.data.length > 0) {
        setResults(originalData);
      } else {
        // If no data or error, just set the original response
        setResults(originalData);

        // Show a toast notification for no results
        if (showToasts && originalData.success && (!Array.isArray(originalData.data) || originalData.data.length === 0)) {
          toast.info('No results found for your search term.', {
            position: "top-right",
            autoClose: 3000
          });
        }
      }

      // Handle pagination - use functional update to avoid dependency on pagination state
      if (response.data.success && Array.isArray(response.data.data)) {
        const totalItems = response.data.data.length;

        // Show success toast with result count
        if (showToasts && totalItems > 0) {
          toast.success(`Found ${totalItems} results for "${searchTerm}"`, {
            position: "top-right",
            autoClose: 3000
          });
        }

        setPagination(prevPagination => {
          const pageSize = prevPagination.pageSize;
          const totalPages = Math.ceil(totalItems / pageSize);
          return {
            ...prevPagination,
            totalItems,
            totalPages
          };
        });
      }

      return true;
    } catch (err) {
      console.error('Error searching term:', err);

      // Handle timeout errors specifically
      let errorMessage = '';
      if (err.code === 'ECONNABORTED') {
        errorMessage = 'Search timed out. Please try a more specific search term.';
        setError(errorMessage);
        if (showToasts) {
          toast.error(errorMessage);
        }
      } else if (err.response && err.response.status === 504) {
        errorMessage = 'Search timed out on the server. Please try a more specific search term.';
        setError(errorMessage);
        if (showToasts) {
          toast.error(errorMessage);
        }
      } else {
        errorMessage = 'Failed to search. Please try again later.';
        setError(errorMessage);
        if (showToasts) {
          toast.error(errorMessage);
        }
      }

      // Clear results
      setResults(null);

      return false;
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array since searchAll doesn't depend on any state

  // Assign the implementation to the ref
  searchAllRef.current = searchAllImpl;

  // Create a stable reference to the search function
  const searchAll = useCallback((...args) => {
    return searchAllRef.current(...args);
  }, []);

  const setPage = useCallback((page) => {
    setPagination(prevPagination => ({
      ...prevPagination,
      page: Math.max(1, Math.min(page, prevPagination.totalPages))
    }));
  }, []);

  const setPageSize = useCallback((size) => {
    const newSize = Math.max(10, Math.min(size, 500)); // Limit page size

    setPagination(prevPagination => {
      const newTotalPages = Math.ceil(prevPagination.totalItems / newSize);
      return {
        ...prevPagination,
        pageSize: newSize,
        totalPages: newTotalPages,
        page: Math.min(prevPagination.page, newTotalPages)
      };
    });
  }, []);

  // Get the current page of results - memoized to prevent re-renders
  const paginatedResults = useMemo(() => {
    if (!results || !results.data || !Array.isArray(results.data)) {
      return results;
    }

    const start = (pagination.page - 1) * pagination.pageSize;
    const end = start + pagination.pageSize;

    // Create a copy of results with paginated data
    return {
      ...results,
      data: results.data.slice(start, end),
      pagination: {
        page: pagination.page,
        pageSize: pagination.pageSize,
        totalItems: pagination.totalItems,
        totalPages: pagination.totalPages,
        currentStart: start + 1,
        currentEnd: Math.min(end, pagination.totalItems)
      }
    };
  }, [results, pagination]);

  return {
    searchAll,
    results: paginatedResults,
    allResults: results,
    loading,
    error,
    pagination,
    setPage,
    setPageSize
  };
}

export default useSearchCSV;
