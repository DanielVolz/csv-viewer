// Mock axios module for testing
const axios = {
  defaults: {
    baseURL: 'http://localhost:8000',
    headers: {
      'Content-Type': 'application/json'
    }
  },
  get: jest.fn((url, config = {}) => {
    if (typeof url === 'string') {
      if (url.includes('/api/files/columns')) {
        return Promise.resolve({
          data: {
            success: true,
            columns: ['File Name', 'MAC Address', 'IP Address', 'Creation Date']
          }
        });
      }
      if (url.includes('/api/files/netspeed_info')) {
        return Promise.resolve({
          data: {
            success: true,
            file_name: 'netspeed.csv',
            size: 12345,
            modified_time: '2025-01-01T00:00:00Z',
            date: '2025-01-01',
            line_count: 2
          }
        });
      }
      if (url.includes('/api/files/preview')) {
        return Promise.resolve({
          data: {
            success: true,
            message: 'CSV File Preview',
            headers: ['IP Address', 'MAC Address', 'Description'],
            data: [
              { 'IP Address': '192.168.1.100', 'MAC Address': 'AA:BB:CC:DD:EE:FF', 'Description': 'Desktop' },
              { 'IP Address': '192.168.1.101', 'MAC Address': 'AA:BB:CC:DD:EE:00', 'Description': 'Laptop' }
            ]
          }
        });
      }
    }
    return Promise.resolve({ data: {} });
  }),
  post: jest.fn(() => Promise.resolve({ data: {} })),
  put: jest.fn(() => Promise.resolve({ data: {} })),
  delete: jest.fn(() => Promise.resolve({ data: {} })),
  // Align with axios API used in components
  isCancel: jest.fn(() => false)
};

export default axios;
