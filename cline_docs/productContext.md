# CSV Viewer - Product Context

## Why This Project Exists

The CSV Data Viewer is designed as a specialized tool for network administrators and IT professionals who need to view and search through network data stored in CSV files. It addresses the challenge of efficiently managing and extracting information from potentially large datasets containing network device information.

## Problems It Solves

1. **Data Accessibility**: Makes CSV data easily accessible through a modern web interface, eliminating the need for spreadsheet software or command-line tools.

2. **Search Efficiency**: Provides powerful search capabilities to quickly find specific network devices by MAC address, IP, or other attributes across current and historical files.

3. **Network Management**: Helps network administrators track devices across their network infrastructure by consolidating information about switch ports, VLANs, and device details.

4. **Historical Data Analysis**: Enables searching through both current and historical network data files, providing visibility into how the network has changed over time.

5. **Performance Optimization**: Offers efficient handling of large CSV datasets through OpenSearch indexing for rapid queries and results.

## How It Should Work

### Core Functionality

1. **File Browsing**: Users can view available CSV files in the system and see basic metadata about each file.

2. **CSV Preview**: Users can preview the contents of CSV files with a customizable number of rows (10, 25, 50, or 100).

3. **Mac Address Search**: Users can search for specific MAC addresses across current and historical files, with results displaying all related network information.

4. **Search Results Display**: 
   - All headers from the CSV file are displayed as column headers in a defined order
   - Each row shows the source file name and creation date
   - Results include row numbers for easy reference
   - Tables adapt to screen size with horizontal scrolling when needed

5. **UI Preferences**: Dark mode support for better viewing in low-light environments, with preferences saved between sessions.

### Implementation Phases

The project was implemented in multiple phases:

1. **Infrastructure and Environment Setup**: Server provisioning, dependency installation, repository setup
2. **Backend Framework Setup**: FastAPI configuration, Celery integration, Redis setup
3. **Frontend Framework Setup**: React application with Material UI and basic components
4. **OpenSearch Setup**: Installation and configuration for data indexing and querying
5. **Component Implementation**:
   - FileInfoBox component (Task 0)
   - CSV table improvements (Task 0.1)
   - Dark mode implementation (Task 0.2)
   - Row number column addition (Task 1.1)
   - MAC address search functionality (Task 1)
6. **Testing Implementation**: Comprehensive test suite covering frontend and backend components (Task 2)

### Testing Approach

The application includes a complete test suite covering:

1. **Frontend Tests**:
   - Component Tests (rendering, user interactions, state management)
   - Hook Tests (initialization, data fetching, error handling)
   - Integration Tests (component interaction)

2. **Backend Tests**:
   - API Endpoint Tests (request handling, response formatting, error cases)
   - Utility Tests (CSV parsing, OpenSearch integration, helper functions)
   - Edge Case Tests (invalid inputs, error conditions)

3. **Test Structure**:
   - Mirrored structure matching application code
   - Jest and React Testing Library for frontend
   - Pytest and FastAPI TestClient for backend

### User Experience

1. The application should provide a responsive, intuitive interface that works across different device sizes.

2. Information should be presented in a clean, organized manner with clear visual distinction between different types of data.

3. Users should receive appropriate feedback during loading states and error conditions.

4. The interface should follow modern web design principles with consistent styling and theme support.

5. The application should perform efficiently even with large CSV files, providing quick search results and smooth scrolling.
