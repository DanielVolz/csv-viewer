# CSV Viewer - Active Context

## Currently Working On

- **Memory Bank Initialization**: Setting up the memory bank documentation for the CSV Viewer project
- **System Familiarization**: Understanding the codebase, architecture, and project requirements

## Recent Changes

- **Memory Bank Creation**: Created initial documentation files:
  - productContext.md - Explaining why the project exists and how it should work
  - systemPatterns.md - Documenting system architecture and patterns
  - techContext.md - Listing technologies used and development setup
  - activeContext.md (this file) - Tracking current work
  - progress.md - Tracking project progress and status

## Next Steps

- **Project Overview Review**: Take a deeper look at specific code components to better understand implementation details
- **Environment Setup Confirmation**: Ensure development environment can be properly started with `./start-app.sh`
- **Feature Exploration**: Interact with the application to understand current functionality and identify potential improvements
- **Implementation Verification**: Compare existing implementation with the requirements outlined in implementation.md

## Notes

- The project follows a specific structure with a React frontend and FastAPI backend
- OpenSearch is used for efficient CSV data searching and indexing
- The application supports both local development and Docker-based deployment
- Major features include CSV file viewing, search functionality, and dark mode support
- Implementation details are documented in the docs/implementation.md file

## Technical Implementation Details

### Component Structure
- **FileInfoBox**: Displays metadata about the current netspeed.csv file (creation date, entry count)
- **CSVSearch**: Provides search functionality across CSV files
- **DarkModeToggle**: Enables switching between light and dark themes
- **FileTable**: Shows available CSV files with metadata
- **FilePreview**: Displays CSV data with adjustable preview limit (10, 25, 50, 100 rows)

