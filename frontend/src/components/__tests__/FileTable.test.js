import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import FileTable from '../FileTable';
import useFiles from '../../hooks/useFiles';

// Mock the useFiles hook
jest.mock('../../hooks/useFiles');

describe('FileTable Component', () => {
  // Mock data for tests
  const mockFiles = [
    {
      name: 'netspeed.csv',
      is_current: true,
      date: '2023-01-01T12:00:00',
      path: '/data/netspeed.csv'
    },
    {
      name: 'netspeed.csv.1',
      is_current: false,
      date: '2022-12-01T12:00:00',
      path: '/data/netspeed.csv.1'
    }
  ];

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders loading state', () => {
    // Mock loading state
    useFiles.mockReturnValue({
      files: [],
      loading: true,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for loading indicator
    expect(screen.getByRole('progressbar')).toBeInTheDocument();
  });

  test('renders error message when there is an error', () => {
    // Mock error state
    const errorMessage = 'Failed to fetch files';
    useFiles.mockReturnValue({
      files: [],
      loading: false,
      error: errorMessage
    });
    
    render(<FileTable />);
    
    // Check for error message
    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  test('renders no files message when files array is empty', () => {
    // Mock empty files array
    useFiles.mockReturnValue({
      files: [],
      loading: false,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for no files message
    expect(screen.getByText('No files found')).toBeInTheDocument();
  });

  test('renders file table with correct data', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for table headers
    expect(screen.getByText('File Name')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Format')).toBeInTheDocument();
    expect(screen.getByText('Creation Date')).toBeInTheDocument();
    expect(screen.getByText('Path')).toBeInTheDocument();
    
    // Check for file data
    expect(screen.getByText('netspeed.csv')).toBeInTheDocument();
    expect(screen.getByText('netspeed.csv.1')).toBeInTheDocument();
    expect(screen.getByText('/data/netspeed.csv')).toBeInTheDocument();
    expect(screen.getByText('/data/netspeed.csv.1')).toBeInTheDocument();
    
    // Check for date formatting - this might be locale-dependent, so we're looking for partial matches
    const dateString = screen.getByText(/1\/1\/2023/);
    expect(dateString).toBeInTheDocument();
  });

  test('renders current and historical chips correctly', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for status chips
    expect(screen.getByText('Current')).toBeInTheDocument();
    expect(screen.getByText('Historical')).toBeInTheDocument();
  });

  test('renders format chips correctly', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for format chips
    expect(screen.getByText('New Format (14 columns)')).toBeInTheDocument();
    expect(screen.getByText('Old Format (11 columns)')).toBeInTheDocument();
  });

  test('renders the correct title and description', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    
    render(<FileTable />);
    
    // Check for title
    expect(screen.getByText('CSV File List')).toBeInTheDocument();
    
    // Check for description
    expect(screen.getByText(/The following CSV files are available/)).toBeInTheDocument();
  });
});
