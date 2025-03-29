/**
 * API configuration utility
 * Provides the base URL for API requests
 */

// Use environment variable if available, or fallback to detecting the current host
const getBaseUrl = () => {
  // Get the backend port from environment variables
  const backendPort = process.env.REACT_APP_BACKEND_PORT || '8000';
  
  // When running in browser context, always use localhost with the backend port
  // This fixes CORS issues when the frontend is running in a Docker container
  return `http://localhost:${backendPort}`;
};

export const API_BASE_URL = getBaseUrl();
