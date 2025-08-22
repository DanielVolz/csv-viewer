// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toBeInTheDocument();
import '@testing-library/jest-dom';
import { act } from 'react';

// Use fake timers by default to prevent long-running intervals from third-party libs
jest.useFakeTimers();

// Suppress React 18 deprecation warnings for ReactDOMTestUtils.act in tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    // Suppress React Testing Library warnings during tests
    const message = args[0];
    if (message && typeof message === 'string') {
      if (message.includes('ReactDOMTestUtils.act is deprecated') ||
          message.includes('Warning: `ReactDOMTestUtils.act`') ||
          message.includes('An update to') && message.includes('inside a test was not wrapped in act')) {
        return; // Suppress these warnings
      }
    }
    // Allow other errors through (but not the testing warnings)
    if (!message || typeof message !== 'string' || !message.includes('Warning:')) {
      originalError.call(console, ...args);
    }
  };
});

afterAll(() => {
  console.error = originalError;
});

// Mock react-toastify to avoid timers and state updates during tests
jest.mock('react-toastify', () => {
  const toast = {
    info: jest.fn(() => 'toast-id'),
    error: jest.fn(() => 'toast-id'),
    success: jest.fn(() => 'toast-id'),
    warning: jest.fn(() => 'toast-id'),
    dismiss: jest.fn(),
  };
  // Render nothing for ToastContainer to avoid container observers
  const ToastContainer = () => null;
  return { __esModule: true, toast, ToastContainer };
});

// Mock matchMedia which is not available in Jest
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // Deprecated
    removeListener: jest.fn(), // Deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Provide a lightweight global fetch mock to prevent real network calls
// Covers: useUpdateNotifier HEAD checks and index status fetches used in tests
// Always replace with a jest.fn so we can control behavior consistently
// eslint-disable-next-line no-undef
global.fetch = jest.fn();
// Ensure all global references point to the same mock
// eslint-disable-next-line no-undef
if (typeof window !== 'undefined') window.fetch = global.fetch;
// eslint-disable-next-line no-undef
if (typeof globalThis !== 'undefined') globalThis.fetch = global.fetch;

const headersMock = {
  get: (name) => {
    const key = String(name || '').toLowerCase();
    if (key === 'etag') return 'test-etag';
    if (key === 'last-modified') return 'Mon, 01 Jan 2024 00:00:00 GMT';
    return null;
  },
};

// Default fetch implementation for tests
global.fetch.mockImplementation(async (url, options = {}) => {
  const u = typeof url === 'string' ? url : '';
  // HEAD checks from useUpdateNotifier
  if (u === '/index.html' || u === '/') {
    return { ok: true, status: 200, headers: headersMock, text: async () => '' };
  }
  // Index status checks used by some components
  if (u.includes('/api/files/index/status')) {
    return { ok: true, status: 200, headers: headersMock, json: async () => ({ state: {} }) };
  }
  // Fallback generic response
  return { ok: true, status: 200, headers: headersMock, json: async () => ({}), text: async () => '' };
});

// Clean up any pending timers and mocks between tests
afterEach(() => {
  try { jest.clearAllTimers(); } catch { }
  try { jest.clearAllMocks(); } catch { }
});

// Provide a stable mock for useColumns so SettingsProvider doesn't hit the network in tests
jest.mock('./hooks/useColumns', () => {
  const defaultColumns = [
    { id: 'File Name', label: 'File Name', enabled: true },
    { id: 'Creation Date', label: 'Creation Date', enabled: true },
    { id: 'IP Address', label: 'IP Address', enabled: true },
    { id: 'MAC Address', label: 'MAC Address', enabled: true },
    { id: 'Description', label: 'Description', enabled: true },
    { id: 'Line Number', label: 'Line Number', enabled: true },
    { id: 'Switch Hostname', label: 'Switch Hostname', enabled: true },
    { id: 'Switch Port', label: 'Switch Port', enabled: true },
    { id: 'Serial Number', label: 'Serial Number', enabled: true },
    { id: 'Model Name', label: 'Model Name', enabled: true },
  ];
  return {
    __esModule: true,
    default: () => ({ columns: defaultColumns, loading: false, error: null, refreshColumns: jest.fn() })
  };
});
