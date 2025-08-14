import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import FileTable from '../FileTable';
import { SettingsProvider } from '../../contexts/SettingsContext';
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
    // Only reset the specific hook mock; do not clear global mocks like fetch
    useFiles.mockReset();
    if (global.fetch && typeof global.fetch.mockClear === 'function') {
      global.fetch.mockClear();
    }
  });

  const renderWithProviders = (ui) => render(<SettingsProvider>{ui}</SettingsProvider>);

  test('renders loading state', () => {
    // Mock loading state
    useFiles.mockReturnValue({
      files: [],
      loading: true,
      error: null
    });
    renderWithProviders(<FileTable />);

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
    renderWithProviders(<FileTable />);

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
    renderWithProviders(<FileTable />);

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
    renderWithProviders(<FileTable />);

    // Check for table headers (current implementation)
    expect(screen.getByText('File Name')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Created')).toBeInTheDocument();
    expect(screen.getByText('Records')).toBeInTheDocument();

    // Check for file names
    expect(screen.getByText('netspeed.csv')).toBeInTheDocument();
    expect(screen.getByText('netspeed.csv.1')).toBeInTheDocument();

    // Check for date strings as rendered (YYYY-MM-DD)
    expect(screen.getByText('2023-01-01')).toBeInTheDocument();
    expect(screen.getByText('2022-12-01')).toBeInTheDocument();
  });

  test('renders current and historical chips correctly', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    renderWithProviders(<FileTable />);

    // Check for status chips (Active for current file, Historical for others)
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Historical')).toBeInTheDocument();
  });

  // The current UI does not display format chips; omit this legacy test

  test('renders the correct title and description', () => {
    // Mock files data
    useFiles.mockReturnValue({
      files: mockFiles,
      loading: false,
      error: null
    });
    renderWithProviders(<FileTable />);

    // Check for title
    expect(screen.getByText('Files')).toBeInTheDocument();
  });
});
