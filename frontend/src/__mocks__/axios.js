// Mock axios module for testing
const axios = {
  defaults: {
    baseURL: 'http://localhost:8000',
    headers: {
      'Content-Type': 'application/json'
    }
  },
  get: jest.fn(() => Promise.resolve({ data: {} })),
  post: jest.fn(() => Promise.resolve({ data: {} })),
  put: jest.fn(() => Promise.resolve({ data: {} })),
  delete: jest.fn(() => Promise.resolve({ data: {} }))
};

export default axios;
