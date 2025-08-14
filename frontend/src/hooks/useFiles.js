import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

/**
 * Custom hook for fetching files from the backend API
 * @returns {Object} { files, loading, error, refetch }
 */
function useFiles() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchFiles = useCallback(async () => {
      try {
        setLoading(true);
        // Call the backend API endpoint
        const response = await axios.get('/api/files/');
        setFiles(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching files:', err);
        setError('Failed to fetch files. Please try again later.');
        // For development, set some mock data to display the UI
        setFiles([
          { name: 'netspeed.csv', path: '../example-data/netspeed.csv', is_current: true },
          { name: 'netspeed.csv.1', path: '../example-data/netspeed.csv.1', is_current: false }
        ]);
      } finally {
        setLoading(false);
      }
  }, []);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const refetch = useCallback(() => {
    fetchFiles();
  }, [fetchFiles]);

  return { files, loading, error, refetch };
}

export default useFiles;
