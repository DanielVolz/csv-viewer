import { renderHook } from '@testing-library/react-hooks';
import { act } from 'react-dom/test-utils';
import axios from 'axios';
import useFilePreview from '../useFilePreview';

// Mock axios
jest.mock('axios');

describe('useFilePreview Hook', () => {
  // Mock data for tests
  const mockPreviewData = {
    success: true,
    message: 'Preview data loaded successfully',
    headers: ['#', 'File Name', 'IP Address', 'MAC Address', 'Extra Column', 'Creation Date'],
    data: [
      {
        '#': '1',
        'File Name': 'netspeed.csv',
        'IP Address': '192.168.1.1',
        'MAC Address': '00:11:22:33:44:55',
        'Extra Column': 'extra data',
        'Creation Date': '2023-01-01T12:00:00'
      },
      {
        '#': '2',
        'File Name': 'netspeed.csv',
        'IP Address': '192.168.1.2',
        'MAC Address': '00:11:22:33:44:66',
        'Extra Column': 'more extra data',
        'Creation Date': '2023-01-01T12:01:00'
      }
    ]
  };
  
  const mockFileInfo = {
    success: true,
    line_count: 1000,
    date: '2023-01-01'
  };

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock console.error to prevent noise in test output
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    // Restore console.error
    console.error.mockRestore();
  });

  test('fetches preview data successfully from API', async () => {
    // Mock successful API calls
    axios.get.mockImplementation((url) => {
      if (url === 'http://localhost:8000/api/files/netspeed_info') {
        return Promise.resolve({ data: mockFileInfo });
      } else if (url === 'http://localhost:8000/api/files/preview') {
        return Promise.resolve({ data: mockPreviewData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    
    // Render the hook with default limit
    const { result, waitForNextUpdate } = renderHook(() => useFilePreview());
    
    // Initially should be in loading state
    expect(result.current.loading).toBe(true);
    expect(result.current.previewData).toBeNull();
    expect(result.current.error).toBeNull();
    
    // Wait for the API calls to complete
    await waitForNextUpdate();
    
    // After API calls, should have data and not be loading
    expect(result.current.loading).toBe(false);
    expect(result.current.previewData).not.toBeNull();
    expect(result.current.error).toBeNull();
    
    // Verify the API calls were made correctly
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/files/netspeed_info');
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/files/preview', {
      params: { limit: 100 } // Default limit
    });
    
    // Check that data was filtered according to the desired order
    const expectedHeaders = ['#', 'File Name', 'Creation Date', 'IP Address', 'MAC Address'];
    expect(result.current.previewData.headers).toEqual(
      expect.arrayContaining(expectedHeaders)
    );
    
    // Line count should come from file info
    expect(result.current.previewData.line_count).toBe(1000);
  });

  test('handles API error and sets fallback data', async () => {
    // Mock API call failure
    axios.get.mockRejectedValue(new Error('Network Error'));
    
    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useFilePreview());
    
    // Initially should be in loading state
    expect(result.current.loading).toBe(true);
    
    // Wait for the API call to complete
    await waitForNextUpdate();
    
    // After API error, should set error message and fallback data
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Failed to fetch file preview. Please try again later.');
    
    // Should have fallback data for development
    expect(result.current.previewData.success).toBe(false);
    expect(result.current.previewData.message).toBe('Error connecting to backend');
    
    // Verify console.error was called
    expect(console.error).toHaveBeenCalled();
  });

  test('passes different limit values to API', async () => {
    // Mock successful API calls
    axios.get.mockImplementation((url) => {
      if (url === 'http://localhost:8000/api/files/netspeed_info') {
        return Promise.resolve({ data: mockFileInfo });
      } else if (url === 'http://localhost:8000/api/files/preview') {
        return Promise.resolve({ data: mockPreviewData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    
    // Render the hook with custom limit
    const customLimit = 50;
    const { waitForNextUpdate } = renderHook(() => useFilePreview(customLimit));
    
    // Wait for the API calls to complete
    await waitForNextUpdate();
    
    // Verify the API call was made with the custom limit
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/files/preview', {
      params: { limit: customLimit }
    });
  });

  test('filters data according to desired column order', async () => {
    // Mock successful API calls
    axios.get.mockImplementation((url) => {
      if (url === 'http://localhost:8000/api/files/netspeed_info') {
        return Promise.resolve({ data: mockFileInfo });
      } else if (url === 'http://localhost:8000/api/files/preview') {
        return Promise.resolve({ data: mockPreviewData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    
    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useFilePreview());
    
    // Wait for the API calls to complete
    await waitForNextUpdate();
    
    // Check that the first data item has been filtered
    const firstDataItem = result.current.previewData.data[0];
    
    // Should have the desired columns in the right order
    expect(Object.keys(firstDataItem)).toContain('#');
    expect(Object.keys(firstDataItem)).toContain('File Name');
    expect(Object.keys(firstDataItem)).toContain('Creation Date');
    expect(Object.keys(firstDataItem)).toContain('IP Address');
    expect(Object.keys(firstDataItem)).toContain('MAC Address');
    
    // Should not have the extra column
    expect(Object.keys(firstDataItem)).not.toContain('Extra Column');
  });

  test('refetches data when limit changes', async () => {
    // Mock successful API calls
    axios.get.mockImplementation((url) => {
      if (url === 'http://localhost:8000/api/files/netspeed_info') {
        return Promise.resolve({ data: mockFileInfo });
      } else if (url === 'http://localhost:8000/api/files/preview') {
        return Promise.resolve({ data: mockPreviewData });
      }
      return Promise.reject(new Error('Unknown URL'));
    });
    
    // Render the hook with initial limit
    const { result, waitForNextUpdate, rerender } = renderHook(
      (initialProps) => useFilePreview(initialProps), 
      { initialProps: 25 }
    );
    
    // Wait for the initial API calls to complete
    await waitForNextUpdate();
    
    // Clear the mock to track new calls
    axios.get.mockClear();
    
    // Rerender with new limit
    rerender(50);
    
    // Wait for the API calls with new limit to complete
    await waitForNextUpdate();
    
    // Verify the API call was made with the new limit
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/files/preview', {
      params: { limit: 50 }
    });
  });
});
