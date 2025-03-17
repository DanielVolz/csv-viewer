import { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * Custom hook for fetching files from the backend API
 * @returns {Object} { files, loading, error }
 */
function useFiles() {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        setLoading(true);
        // Call the backend API endpoint
        const response = await axios.get('http://localhost:8000/api/files/');
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
    };

    fetchFiles();
  }, []);

  return { files, loading, error };
}

export default useFiles;
