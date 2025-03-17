import { useState } from 'react';
import axios from 'axios';

/**
 * Custom hook for searching MAC addresses in the backend API
 * @returns {Object} { search, results, loading, error }
 */
function useSearchMacAddress() {
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = async (macAddress, includeHistorical = true) => {
    // Validate MAC address format
    const macRegex = /^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$|^([0-9A-Fa-f]{12})$/;
    if (!macRegex.test(macAddress)) {
      setError('Invalid MAC address format. Please use format like 00:1A:2B:3C:4D:5E');
      return false;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Call the backend API endpoint
      const response = await axios.get('http://localhost:8000/api/search/', {
        params: {
          mac_address: macAddress,
          include_historical: includeHistorical
        }
      });
      
      setResults(response.data);
      return true;
    } catch (err) {
      console.error('Error searching MAC address:', err);
      setError('Failed to search MAC address. Please try again later.');
      
      // For development, set mock results
      setResults({
        success: false,
        message: 'Error connecting to backend',
        headers: [
          'ip_address', 'mac_address', 'serial_number', 'vlan', 
          'subnet', 'phone_number', 'switch_host_url', 'switch_interface'
        ],
        data: null
      });
      
      return false;
    } finally {
      setLoading(false);
    }
  };

  return { search, results, loading, error };
}

export default useSearchMacAddress;
