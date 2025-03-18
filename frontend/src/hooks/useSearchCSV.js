import { useState } from 'react';
import axios from 'axios';

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

  const searchAll = async (searchTerm, includeHistorical = true) => {
    if (!searchTerm) {
      setError('Please enter a search term');
      return false;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Call the backend API endpoint
      const response = await axios.get('http://localhost:8000/api/search/', {
        params: {
          query: searchTerm,
          field: null, // Always search in all fields
          include_historical: includeHistorical
        },
        timeout: 30000 // 30 second timeout
      });
      
      setResults(response.data);
      
      // Handle pagination
      if (response.data.success && Array.isArray(response.data.data)) {
        const totalItems = response.data.data.length;
        const pageSize = pagination.pageSize;
        const totalPages = Math.ceil(totalItems / pageSize);
        
        setPagination({
          ...pagination,
          totalItems,
          totalPages
        });
      }
      
      return true;
    } catch (err) {
      console.error('Error searching term:', err);
      
      // Handle timeout errors specifically
      if (err.code === 'ECONNABORTED') {
        setError('Search timed out. Please try a more specific search term.');
      } else if (err.response && err.response.status === 504) {
        setError('Search timed out on the server. Please try a more specific search term.');
      } else {
        setError('Failed to search. Please try again later.');
      }
      
      // Clear results
      setResults(null);
      
      return false;
    } finally {
      setLoading(false);
    }
  };
  
  const setPage = (page) => {
    setPagination({
      ...pagination,
      page: Math.max(1, Math.min(page, pagination.totalPages))
    });
  };
  
  const setPageSize = (size) => {
    const newSize = Math.max(10, Math.min(size, 500)); // Limit page size
    const newTotalPages = Math.ceil(pagination.totalItems / newSize);
    
    setPagination({
      ...pagination,
      pageSize: newSize,
      totalPages: newTotalPages,
      page: Math.min(pagination.page, newTotalPages)
    });
  };
  
  // Get the current page of results
  const paginatedResults = () => {
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
        ...pagination,
        currentStart: start + 1,
        currentEnd: Math.min(end, pagination.totalItems)
      }
    };
  };

  return { 
    searchAll, 
    results: paginatedResults(), 
    allResults: results,
    loading, 
    error, 
    pagination,
    setPage,
    setPageSize
  };
}

export default useSearchCSV;
