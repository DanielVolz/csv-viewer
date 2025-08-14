import { renderHook } from '@testing-library/react-hooks';
import { act } from 'react-dom/test-utils';
import axios from 'axios';
import useSearchCSV from '../useSearchCSV';

// Mock axios
jest.mock('axios');

describe('useSearchCSV Hook', () => {
  // Mock data for tests
  const mockSearchResults = {
    success: true,
    message: 'Found 2 results',
    headers: ['File Name', 'Creation Date', 'IP Address', 'Line Number', 'MAC Address', 'Extra Header'],
    data: [
      {
        'File Name': 'netspeed.csv',
        'Creation Date': '2023-01-01T12:00:00',
        'IP Address': '192.168.1.1',
        'Line Number': '1',
        'MAC Address': '00:11:22:33:44:55',
        'Extra Header': 'extra data'
      },
      {
        'File Name': 'netspeed.csv',
        'Creation Date': '2023-01-01T12:00:00',
        'IP Address': '192.168.1.2',
        'Line Number': '2',
        'MAC Address': '00:11:22:33:44:66',
        'Extra Header': 'more extra data'
      }
    ]
  };

  beforeEach(() => {
    jest.clearAllMocks();

    // Mock console.error to prevent noise in test output
    jest.spyOn(console, 'error').mockImplementation(() => { });
  });

  afterEach(() => {
    // Restore console.error
    console.error.mockRestore();
  });

  test('initializes with correct defaults', () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Check for initial state
    expect(result.current.results).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();

    // Check for pagination defaults
    expect(result.current.pagination).toEqual({
      page: 1,
      pageSize: 100,
      totalItems: 0,
      totalPages: 0
    });
  });

  test('performs search successfully', async () => {
    // Mock successful API call
    axios.get.mockResolvedValue({ data: mockSearchResults });

    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useSearchCSV());

    // Perform search
    let success;
    act(() => {
      success = result.current.searchAll('192.168.1', true);
    });

    // Initially should be in loading state
    expect(result.current.loading).toBe(true);

    // Wait for the API call to complete
    await waitForNextUpdate();

    // Should have resolved to true
    await expect(success).resolves.toBe(true);

    // After API call, should have results data and not be loading
    expect(result.current.loading).toBe(false);
    expect(result.current.results).not.toBeNull();
    expect(result.current.error).toBeNull();

    // Verify the API call was made correctly
    expect(axios.get).toHaveBeenCalledWith('/api/search/', {
      params: {
        query: '192.168.1',
        field: null,
        include_historical: true
      },
      timeout: 30000
    });


    // Pagination should be updated
    expect(result.current.pagination.totalItems).toBe(2);
    expect(result.current.pagination.totalPages).toBe(1);
  });

  test('returns error when search term is empty', async () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Perform search with empty term
    let success;
    act(() => {
      success = result.current.searchAll('');
    });

    // Should have resolved to false
    await expect(success).resolves.toBe(false);

    // Should have error message
    expect(result.current.error).toBe('Please enter a search term');

    // API should not have been called
    expect(axios.get).not.toHaveBeenCalled();
  });

  test('handles API error', async () => {
    // Mock API call failure
    axios.get.mockRejectedValue(new Error('Network Error'));

    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useSearchCSV());

    // Perform search
    let success;
    act(() => {
      success = result.current.searchAll('192.168.1', true);
    });

    // Wait for the API call to complete
    await waitForNextUpdate();

    // Should have resolved to false
    await expect(success).resolves.toBe(false);

    // After API error, should set error message and clear results
    expect(result.current.loading).toBe(false);
    expect(result.current.results).toBeNull();
    expect(result.current.error).toBe('Failed to search. Please try again later.');

    // Verify console.error was called
    expect(console.error).toHaveBeenCalled();
  });

  test('handles timeout error', async () => {
    // Mock timeout error
    const timeoutError = new Error('Timeout');
    timeoutError.code = 'ECONNABORTED';
    axios.get.mockRejectedValue(timeoutError);

    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useSearchCSV());

    // Perform search
    act(() => {
      result.current.searchAll('192.168.1', true);
    });

    // Wait for the API call to complete
    await waitForNextUpdate();

    // After timeout, should set specific error message
    expect(result.current.error).toBe('Search timed out. Please try a more specific search term.');
  });

  test('handles server timeout error', async () => {
    // Mock server timeout error
    axios.get.mockRejectedValue({
      response: {
        status: 504
      }
    });

    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useSearchCSV());

    // Perform search
    act(() => {
      result.current.searchAll('192.168.1', true);
    });

    // Wait for the API call to complete
    await waitForNextUpdate();

    // After server timeout, should set specific error message
    expect(result.current.error).toBe('Search timed out on the server. Please try a more specific search term.');
  });

  test('allows changing page', () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Set up pagination state with more pages
    act(() => {
      result.current.pagination.totalPages = 5;
    });

    // Change page
    act(() => {
      result.current.setPage(3);
    });

    // Page should be updated
    expect(result.current.pagination.page).toBe(3);
  });

  test('prevents setting page beyond limits', () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Set up pagination state with more pages
    act(() => {
      result.current.pagination.totalPages = 5;
    });

    // Try to set page too low
    act(() => {
      result.current.setPage(0);
    });

    // Page should be limited to minimum
    expect(result.current.pagination.page).toBe(1);

    // Try to set page too high
    act(() => {
      result.current.setPage(10);
    });

    // Page should be limited to maximum
    expect(result.current.pagination.page).toBe(5);
  });

  test('allows changing page size', () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Set up pagination state with items
    act(() => {
      result.current.pagination.totalItems = 200;
    });

    // Change page size
    act(() => {
      result.current.setPageSize(50);
    });

    // Page size should be updated
    expect(result.current.pagination.pageSize).toBe(50);

    // Total pages should be recalculated
    expect(result.current.pagination.totalPages).toBe(4);
  });

  test('limits page size to valid range', () => {
    // Render the hook
    const { result } = renderHook(() => useSearchCSV());

    // Try to set page size too low
    act(() => {
      result.current.setPageSize(5);
    });

    // Page size should be limited to minimum
    expect(result.current.pagination.pageSize).toBe(10);

    // Try to set page size too high
    act(() => {
      result.current.setPageSize(1000);
    });

    // Page size should be limited to maximum
    expect(result.current.pagination.pageSize).toBe(500);
  });

  test('provides paginated results', async () => {
    // Create a larger mock result set
    const largeResults = {
      ...mockSearchResults,
      data: Array(150).fill().map((_, i) => ({
        'File Name': 'netspeed.csv',
        'Creation Date': '2023-01-01T12:00:00',
        'IP Address': `192.168.1.${i}`,
        'Line Number': `${i + 1}`,
        'MAC Address': '00:11:22:33:44:55'
      }))
    };

    // Mock successful API call
    axios.get.mockResolvedValue({ data: largeResults });

    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useSearchCSV());

    // Perform search
    act(() => {
      result.current.searchAll('192.168.1', true);
    });

    // Wait for the API call to complete
    await waitForNextUpdate();

    // Page 1 results should contain items 0-99
    expect(result.current.results.data.length).toBe(100);
    expect(result.current.results.data[0]['IP Address']).toBe('192.168.1.0');
    expect(result.current.results.data[99]['IP Address']).toBe('192.168.1.99');

    // Pagination info should be correct
    expect(result.current.results.pagination.currentStart).toBe(1);
    expect(result.current.results.pagination.currentEnd).toBe(100);

    // Change to page 2
    act(() => {
      result.current.setPage(2);
    });

    // Page 2 results should contain items 100-149
    expect(result.current.results.data.length).toBe(50);
    expect(result.current.results.data[0]['IP Address']).toBe('192.168.1.100');
    expect(result.current.results.data[49]['IP Address']).toBe('192.168.1.149');

    // Pagination info should be updated
    expect(result.current.results.pagination.currentStart).toBe(101);
    expect(result.current.results.pagination.currentEnd).toBe(150);
  });
});
