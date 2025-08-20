module.exports = {
  // Use babel-jest to transform JavaScript files
  transform: {
    "^.+\\.(js|jsx)$": "babel-jest"
  },

  // Tell Jest to mock the axios module
  moduleNameMapper: {
    "^axios$": "<rootDir>/src/__mocks__/axios.js"
  },

  // Ignore node_modules except for specific packages that need transformation
  transformIgnorePatterns: [
    "/node_modules/(?!(axios)/).+\\.js$"
  ],

  // Set up test environment for React components
  testEnvironment: "jsdom",
  testEnvironmentOptions: {
    resources: "usable",
    runScripts: "dangerously"
  },

  // Setup files to run before each test
  setupFilesAfterEnv: ["<rootDir>/src/setupTests.js"],

  // Use Babel configuration
  testMatch: ["**/__tests__/**/*.js", "**/?(*.)+(spec|test).js"],

  // Root directory is the frontend folder
  roots: ["<rootDir>/src"],

  // Clear mocks between tests
  clearMocks: true,
  // Ensure Jest exits after tests even if open handles remain (safety)
  forceExit: true,
  // Run tests in band to avoid CPU spikes in CI containers
  maxWorkers: 1
};
