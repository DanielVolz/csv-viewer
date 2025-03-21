import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import axios from 'axios';
import FileInfoBox from '../FileInfoBox';

// Mock axios
jest.mock('axios');

describe('FileInfoBox Component', () => {
  // Mock data for testing
  const mockFileInfo = {
    success: true,
    date: '2025-03-15',
    line_count: 1234,
    file_name: 'netspeed.csv',
    size: '156KB'
  };

  const mockErrorResponse = {
    success: false,
    message: 'Could not retrieve file information'
  };

  beforeEach(() => {
    // Clear all mocks before each test
    jest.clearAllMocks();
  });

  it('displays loading indicator while fetching data', () => {
    // Mock axios to return a promise that doesn't resolve immediately
    axios.get.mockImplementation(() => new Promise((resolve) => {
      // This promise doesn't resolve immediately, so component will show loading state
      setTimeout(() => {
        resolve({ data: mockFileInfo });
      }, 500);
    }));

    render(<FileInfoBox />);
    
    // Check if loading indicator is displayed
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  it('displays file information when data is loaded successfully', async () => {
    // Mock successful API response
    axios.get.mockResolvedValue({ data: mockFileInfo });

    render(<FileInfoBox />);
    
    // Initially should show loading state
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
    
    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Current CSV File Information')).toBeInTheDocument();
    });
    
    // Check if file info is displayed correctly
    expect(screen.getByText('netspeed.csv')).toBeInTheDocument();
    expect(screen.getByText('2025-03-15')).toBeInTheDocument();
    expect(screen.getByText('1,234 lines')).toBeInTheDocument();
    
    // Verify API call
    expect(axios.get).toHaveBeenCalledWith('/api/files/netspeed_info');
  });

  it('displays error message when API call fails', async () => {
    // Mock API error
    axios.get.mockRejectedValue(new Error('Network error'));

    render(<FileInfoBox />);
    
    // Wait for error message to display
    await waitFor(() => {
      expect(screen.getByText('Error fetching file information. Please try again later.')).toBeInTheDocument();
    });
    
    // Check if error message is displayed
    expect(screen.queryByText('Current CSV File Information')).not.toBeInTheDocument();
  });

  it('displays server error message when server returns error', async () => {
    // Mock server error response
    axios.get.mockResolvedValue({ data: mockErrorResponse });

    render(<FileInfoBox />);
    
    // Wait for error message to display
    await waitFor(() => {
      expect(screen.getByText('Could not retrieve file information')).toBeInTheDocument();
    });
  });

  it('displays default error message when server returns error without message', async () => {
    // Mock server error response without specific message
    axios.get.mockResolvedValue({ data: { success: false }});

    render(<FileInfoBox />);
    
    // Wait for error message to display
    await waitFor(() => {
      expect(screen.getByText('Failed to fetch file information')).toBeInTheDocument();
    });
  });

  it('displays UI elements correctly when data is loaded', async () => {
    // Mock successful API response
    axios.get.mockResolvedValue({ data: mockFileInfo });

    render(<FileInfoBox />);
    
    // Wait for data to load
    await waitFor(() => {
      expect(screen.getByText('Current CSV File Information')).toBeInTheDocument();
    });
    
    // Check for UI elements
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('FILE NAME')).toBeInTheDocument();
    expect(screen.getByText('CREATED ON')).toBeInTheDocument();
    expect(screen.getByText('PHONE ENTRIES')).toBeInTheDocument();
  });

  it('logs error to console when API call fails', async () => {
    // Spy on console.error
    const consoleErrorSpy = jest.spyOn(console, 'error');
    consoleErrorSpy.mockImplementation(() => {});
    
    // Mock API error
    const error = new Error('Network error');
    axios.get.mockRejectedValue(error);

    render(<FileInfoBox />);
    
    // Wait for error message to display
    await waitFor(() => {
      expect(screen.getByText('Error fetching file information. Please try again later.')).toBeInTheDocument();
    });
    
    // Check if error was logged to console
    expect(consoleErrorSpy).toHaveBeenCalledWith('Error fetching file info:', error);
    
    // Restore console.error
    consoleErrorSpy.mockRestore();
  });
});
