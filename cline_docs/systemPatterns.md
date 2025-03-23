# CSV Viewer - System Patterns

## How the System is Built

The CSV Viewer follows a modern client-server architecture with clear separation of concerns:

### Architecture Overview

1. **Frontend Layer**: React-based user interface
2. **Backend Layer**: FastAPI-based API server
3. **Data Processing Layer**: Celery workers for asynchronous tasks
4. **Search Layer**: OpenSearch for efficient data indexing/querying
5. **Message Broker**: Redis for task queue management

### Data Flow

1. CSV files are stored in a designated `/data` directory
2. Files are indexed into OpenSearch for efficient querying
3. Backend API endpoints provide file listing, preview, and search functionality
4. Frontend components fetch and display data from these endpoints
5. User interactions trigger appropriate API calls and state updates

## Key Technical Decisions

### API Framework: FastAPI

- **Rationale**: Chosen for its high performance, built-in async support, and automatic API documentation
- **Implementation**: Structured as a modular application with dedicated routers for files and search functions
- **Benefits**: Provides type checking, validation, and OpenAPI documentation automatically

### Frontend Library: React with Material UI

- **Rationale**: Selected for component reusability, virtual DOM efficiency, and rich ecosystem
- **Implementation**: Custom hooks for data fetching, context for state management
- **Benefits**: Enables responsive UI, theme customization, and consistent component styling

### State Management: React Context API

- **Rationale**: Used instead of Redux due to simpler implementation for medium-complexity app
- **Implementation**: Theme context for light/dark mode, potential for additional contexts as needed
- **Benefits**: Avoids prop drilling while maintaining readable component logic

### Search Engine: OpenSearch

- **Rationale**: Provides powerful full-text search capabilities with high performance
- **Implementation**: Custom indexing and query building for CSV data
- **Benefits**: Enables efficient searching across large datasets with relevance scoring

#### OpenSearch Integration Details

- **Field Type Definitions**:
  - `keyword_type` for simple string fields requiring exact matches
  - `text_with_keyword` for fields requiring both full-text and exact matching

- **Query Building**:
  - Specialized `_build_query_body` method for query construction
  - Handles field-specific searches with precise matching
  - Supports multi-field searches with relevance scoring
  - Special handling for identifier fields (Line Number, MAC Address)

- **Data Deduplication**:
  - Document deduplication based on composite keys
  - Uses MAC Address and File Name to identify unique records
  - Prevents duplicate results when searching across multiple indices

- **Configuration Management**:
  - Centralized connection parameters for maintainability
  - Environment variables for secure credential storage

### Task Queue: Celery with Redis

- **Rationale**: Enables asynchronous processing for resource-intensive operations
- **Implementation**: Used for search operations and file indexing
- **Benefits**: Prevents blocking the main API thread, improves responsiveness

### Testing: Jest and Pytest

- **Rationale**: Industry standard testing frameworks with good ecosystem support
- **Implementation**: Component tests, hook tests, API endpoint tests, utility tests
- **Benefits**: Ensures code quality, prevents regressions, documents behavior

## Architecture Patterns

### API-First Design

- Backend endpoints are designed before implementing frontend features
- Strong API contracts ensure clear separation between frontend and backend
- Each endpoint has a single responsibility

### Custom React Hooks

- Data fetching logic is encapsulated in custom hooks (`useFiles`, `useFilePreview`, `useSearchCSV`)
- Separates UI rendering from data management
- Promotes reusability and testability

### Component-Based UI

- Interface is broken down into focused, reusable components
- Each component has a specific responsibility
- Component composition creates the full user experience

### Repository Pattern

- Data access logic is abstracted into dedicated utility modules
- CSV operations and OpenSearch interactions are encapsulated
- Makes the codebase more maintainable and testable

### Configuration Management

- Environment variables used for sensitive configuration
- Docker environment setup for consistent deployment
- Separate configuration files for different environments (development, testing)

### Containerization

- Docker and Docker Compose for consistent environments
- Service isolation with defined dependencies
- Volume mapping for persistent data storage
