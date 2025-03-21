# CSV Viewer Tests

This directory contains tests for the backend components of the CSV Viewer application.

## Structure

```
tests/
├── backend/           # Backend tests
│   ├── api/           # API endpoint tests
│   │   ├── test_files.py
│   │   └── test_search.py
│   ├── utils/         # Utility function tests
│   │   ├── test_csv_utils.py
│   │   └── test_opensearch.py
│   └── conftest.py    # Pytest configuration for backend tests
└── README.md          # This file
```

## Running Tests

### Backend Tests

The backend tests use pytest. To run all backend tests:

```bash
cd /path/to/csv-viewer
python -m pytest tests/backend
```

To run a specific test file:

```bash
python -m pytest tests/backend/api/test_files.py
```

### Frontend Tests

The frontend tests have been moved to the standard React project structure in their respective `__tests__` directories within each component and hook folder:

- Component tests are now in `frontend/src/components/__tests__/`
- Hook tests are now in `frontend/src/hooks/__tests__/`

To run all frontend tests:

```bash
cd /path/to/csv-viewer/frontend
npm test
```

To run a specific test file:

```bash
cd /path/to/csv-viewer/frontend
npm test -- -t 'CSVSearch'  # Runs tests with CSVSearch in the name
```

## Test Conventions

### Backend Tests

- Backend tests use pytest fixtures defined in conftest.py
- Mock objects are used for external dependencies
- Tests are grouped by module and function

### Frontend Tests

- Frontend tests use Jest with React Testing Library
- Component tests verify rendering and interactions
- Hook tests verify custom hook behavior
- All API calls are mocked to avoid actual network requests

## Important Notes

- Backend tests add the project root to the Python path to resolve imports correctly
- Frontend tests use relative imports from the project structure
- Tests are designed to run without requiring a database or OpenSearch instance
