# CSV Viewer Application

## Project Overview

This application provides a modern, responsive interface for viewing, searching, and analyzing CSV files containing network speed data. It is designed to efficiently handle both current and historical CSV files, with a focus on performance and user experience.

## Architecture

The application follows a client-server architecture with the following components:

### Backend Components
- **FastAPI:** Provides RESTful API endpoints for file operations and search functionality
- **Celery:** Handles asynchronous tasks like search operations and file indexing
- **Redis:** Serves as a message broker for Celery tasks
- **OpenSearch:** Provides efficient indexing and searching capabilities for CSV data

### Frontend Components
- **React:** Creates a dynamic, responsive user interface
- **Material UI:** Provides modern UI components and theming
- **Axios:** Handles HTTP requests to the backend API

## Implementation Phases

The project was implemented in multiple phases:

1. **Infrastructure and Environment Setup:** Server provisioning, dependency installation, repository setup
2. **Backend Framework Setup:** FastAPI configuration, Celery integration, Redis setup
3. **Frontend Framework Setup:** React application with Material UI and basic components
4. **OpenSearch Setup:** Installation and configuration for data indexing and querying

## Key Features

### Current File Information
- The FileInfoBox component displays metadata about the current CSV file
- Shows creation date and total number of entries

### CSV Data Viewing
- Customized table display with specific column ordering
- Dynamic entry count and user-adjustable preview size
- Row numbering for easy reference

### Dark Mode Support
- Theme toggle for light and dark mode preferences
- Persistent theme settings
- System preference detection

### Search Functionality
- General search across all fields
- Option to include or exclude historical files in search
- Efficient search using OpenSearch backend

### Responsive Design
- Tables and components adapt to different screen sizes
- Horizontal scrolling for tables with many columns
- Proper sizing and spacing for all UI elements

## Technology Stack

### Backend Technologies
- **Python 3.x:** Main programming language
- **FastAPI:** Web framework for API endpoints
- **Celery:** Distributed task queue
- **Redis:** Message broker
- **OpenSearch:** Search and analytics engine
- **Pandas:** Data manipulation and analysis

### Frontend Technologies
- **JavaScript/ES6:** Main programming language
- **React:** UI library
- **Material UI:** Component library
- **Axios:** HTTP client
- **Context API:** State management
- **CSS-in-JS:** Styling solution

## Data Flow

1. CSV files are stored in a designated data directory
2. Files are indexed into OpenSearch for efficient querying
3. Backend API provides endpoints for file listing, preview, and search
4. Frontend components fetch and display data from these endpoints
5. User interactions (search, pagination, etc.) trigger appropriate API calls

## Testing

### Comprehensive Test Suite

The application includes a complete test suite covering both frontend and backend components:

#### Frontend Tests
- **Component Tests:** Verify rendering, user interactions, and state management for all React components
- **Hook Tests:** Check initialization, data fetching, error handling, and state updates for all custom hooks
- **Integration Tests:** Ensure components work together properly

#### Backend Tests
- **API Endpoint Tests:** Validate request handling, response formatting, and error cases for all endpoints
- **Utility Tests:** Verify CSV parsing, OpenSearch integration, and helper functions
- **Edge Case Tests:** Check behavior with invalid inputs and error conditions

### Test Structure
- Tests are organized in a mirrored structure that matches the application code
- Frontend tests use Jest and React Testing Library
- Backend tests use pytest and FastAPI TestClient
- Mocks and fixtures are used to isolate components for targeted testing

### Running Tests
- Frontend tests are executed using npm test commands
- Backend tests are run using pytest
- Documentation in tests/README.md provides detailed instructions

## Future Enhancements

Potential future enhancements could include:

1. Advanced filtering options for CSV data
2. Data visualization with charts and graphs
3. Export functionality for search results
4. User authentication and role-based access control
5. API rate limiting and additional security measures
