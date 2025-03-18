import { useState, useEffect } from 'react';
import axios from 'axios';

/**
 * Custom hook for fetching a preview of the current CSV file from the backend API
 * @param {number} limit - Maximum number of entries to fetch
 * @returns {Object} { previewData, loading, error }
 */
function useFilePreview(limit = 25) {
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPreview = async () => {
      try {
        setLoading(true);
        // Call the backend API endpoint
        const response = await axios.get('http://localhost:8000/api/files/preview', {
          params: { limit }
        });
        setPreviewData(response.data);
        setError(null);
      } catch (err) {
        console.error('Error fetching file preview:', err);
        setError('Failed to fetch file preview. Please try again later.');
        // For development, set some mock data
        setPreviewData({
          success: false,
          message: 'Error connecting to backend',
          headers: [
            'File Name', 'Creation Date', 'IP Address', 'Line Number', 'MAC Address', 
            'Subnet Mask', 'Voice VLAN', 'Switch Hostname', 'Switch Port', 
            'Serial Number', 'Model Name'
          ],
          data: []
        });
      } finally {
        setLoading(false);
      }
    };

    fetchPreview();
  }, [limit]);

  return { previewData, loading, error };
}

export default useFilePreview;
