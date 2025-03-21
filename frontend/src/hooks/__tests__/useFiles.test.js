import { renderHook } from '@testing-library/react-hooks';
import axios from 'axios';
import useFiles from '../useFiles';

// Mock axios
jest.mock('axios');

describe('useFiles Hook', () => {
  // Mock data for tests
  const mockFiles = [
    { name: 'netspeed.csv', path: '/data/netspeed.csv', is_current: true, date: '2023-01-01' },
    { name: 'netspeed.csv.1', path: '/data/netspeed.csv.1', is_current: false, date: '2022-12-01' }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Mock console.error to prevent noise in test output
    jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    // Restore console.error
    console.error.mockRestore();
  });

  test('fetches files successfully from API', async () => {
    // Mock successful API call
    axios.get.mockResolvedValue({ data: mockFiles });
    
    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useFiles());
    
    // Initially should be in loading state with empty files array
    expect(result.current.loading).toBe(true);
    expect(result.current.files).toEqual([]);
    expect(result.current.error).toBeNull();
    
    // Wait for the API call to complete
    await waitForNextUpdate();
    
    // After API call, should have files data and not be loading
    expect(result.current.loading).toBe(false);
    expect(result.current.files).toEqual(mockFiles);
    expect(result.current.error).toBeNull();
    
    // Verify the API call was made correctly
    expect(axios.get).toHaveBeenCalledWith('http://localhost:8000/api/files/');
  });

  test('handles API error and sets fallback data', async () => {
    // Mock API call failure
    axios.get.mockRejectedValue(new Error('Network Error'));
    
    // Render the hook
    const { result, waitForNextUpdate } = renderHook(() => useFiles());
    
    // Initially should be in loading state
    expect(result.current.loading).toBe(true);
    
    // Wait for the API call to complete
    await waitForNextUpdate();
    
    // After API error, should set error message and fallback data
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBe('Failed to fetch files. Please try again later.');
    
    // Should have fallback data for development
    expect(result.current.files).toEqual([
      { name: 'netspeed.csv', path: '../example-data/netspeed.csv', is_current: true },
      { name: 'netspeed.csv.1', path: '../example-data/netspeed.csv.1', is_current: false }
    ]);
    
    // Verify console.error was called
    expect(console.error).toHaveBeenCalled();
  });

  test('initializes with empty files array', () => {
    // Mock API call that will never resolve during this test
    axios.get.mockImplementation(() => new Promise(() => {}));
    
    // Render the hook
    const { result } = renderHook(() => useFiles());
    
    // Initially should have empty files array
    expect(result.current.files).toEqual([]);
  });

  test('initializes with loading state', () => {
    // Mock API call that will never resolve during this test
    axios.get.mockImplementation(() => new Promise(() => {}));
    
    // Render the hook
    const { result } = renderHook(() => useFiles());
    
    // Initially should be in loading state
    expect(result.current.loading).toBe(true);
  });

  test('only makes one API call on multiple renders', async () => {
    // Mock successful API call
    axios.get.mockResolvedValue({ data: mockFiles });
    
    // Render the hook
    const { rerender, waitForNextUpdate } = renderHook(() => useFiles());
    
    // Wait for the initial API call to complete
    await waitForNextUpdate();
    
    // Clear the mock to track new calls
    axios.get.mockClear();
    
    // Rerender the hook
    rerender();
    
    // Verify the API was not called again
    expect(axios.get).not.toHaveBeenCalled();
  });
});
