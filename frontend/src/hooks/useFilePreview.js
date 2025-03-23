import { useState, useEffect } from 'react';
import axios from 'axios';
import { toast } from 'react-toastify';

// Define the desired column order
const DESIRED_ORDER = [
  "#",
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
 * Custom hook for fetching a preview of the current CSV file from the backend API
 * @param {number} limit - Maximum number of entries to fetch
 * @returns {Object} { previewData, loading, error }
 */
function useFilePreview(limit = 105) { // Changed default from 25 to 100
  const [previewData, setPreviewData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPreview = async () => {
      try {
        setLoading(true);
        // Get file info to get the total count
        const infoResponse = await axios.get('http://localhost:8000/api/files/netspeed_info');
        const fileInfo = infoResponse.data;

        // Call the backend API endpoint for preview data
        const response = await axios.get('http://localhost:8000/api/files/preview', {
          params: { limit }
        });

        // Get the original data
        const originalData = response.data;

        // Apply the desired column order
        const filteredHeaders = DESIRED_ORDER.filter(header =>
          originalData.headers.includes(header)
        );

        // Create new data rows with only the desired columns in the specified order
        const filteredData = originalData.data.map(row => {
          const newRow = {};
          filteredHeaders.forEach(header => {
            newRow[header] = row[header];
          });
          return newRow;
        });

        // Set the filtered data with the line count from the info endpoint
        setPreviewData({
          ...originalData,
          headers: filteredHeaders,
          data: filteredData,
          line_count: fileInfo.line_count || 0
        });

        setError(null);
      } catch (err) {
        console.error('Error fetching file preview:', err);
        const errorMessage = 'Failed to fetch file preview. Please try again later.';
        setError(errorMessage);
        toast.error(errorMessage, {
          position: "top-right",
          autoClose: 5000
        });
        // For development, set some mock data with only the desired columns
        setPreviewData({
          success: false,
          message: 'Error connecting to backend',
          headers: DESIRED_ORDER,
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
