/**
 * API configuration utility
 * Provides the base URL for API requests
 */

// Use environment variable if available, or fallback to detecting the current host
const getBaseUrl = () => {
  // First try environment variable
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  
  // If not available, dynamically determine the host
  // This handles both development and production environments
  const { hostname } = window.location;
  
  // If we're accessing via IP or domain name, point to same host but backend port
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `http://${hostname}:8000`;
  }
  
  // Default for local development
  return 'http://localhost:8000';
};

export const API_BASE_URL = getBaseUrl();
