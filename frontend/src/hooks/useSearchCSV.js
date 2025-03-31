import { useState } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

// Define the desired column order - same as in useFilePreview.js
const DESIRED_ORDER = [
  "File Name",
  "Creation Date",
  "IP Address",
  "Line Number",
  "MAC Address",
  "Subnet Mask",
  "Voice VLAN",
  "Switch Hostname",
  "Switch Port",
  "Serial Number",
  "Model Name"
];

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

  const searchAll = async (searchTerm, includeHistorical = true, showToasts = true) => {
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
      
      // Apply the desired column order if there's data
      if (originalData.success && Array.isArray(originalData.data) && originalData.data.length > 0) {
        // Determine all available columns from the first row
        const availableColumns = Object.keys(originalData.data[0]);
        
        // Filter the desired columns that are actually present in the data
        const filteredHeaders = DESIRED_ORDER.filter(header => 
          availableColumns.includes(header)
        );
        
        // Create new data rows with only the desired columns in the specified order
        const filteredData = originalData.data.map(row => {
          const newRow = {};
          filteredHeaders.forEach(header => {
            newRow[header] = row[header];
          });
          return newRow;
        });
        
        // Set the filtered data
        setResults({
          ...originalData,
          headers: filteredHeaders,
          data: filteredData
        });
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
      
      // Handle pagination
      if (response.data.success && Array.isArray(response.data.data)) {
        const totalItems = response.data.data.length;
        const pageSize = pagination.pageSize;
        const totalPages = Math.ceil(totalItems / pageSize);
        
        // Show success toast with result count
        if (showToasts && totalItems > 0) {
          toast.success(`Found ${totalItems} results for "${searchTerm}"`, {
            position: "top-right",
            autoClose: 3000
          });
        }
        
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
