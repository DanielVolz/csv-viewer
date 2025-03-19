# Implementation Tasks

## Task 0: FileInfoBox Component Implementation

### Objective
Create an information box component above the search field to display details about the current netspeed.csv file, including its creation date and the number of phone entries (lines) in the file.

### Technical Requirements

#### Backend (FastAPI)

1. **Create Netspeed Info API Endpoint**
   - Implement a new `/api/files/netspeed_info` endpoint
   - Return the creation date of the current netspeed.csv file
   - Count and return the number of lines in the file (excluding the header)

#### Frontend (React)

1. **Create FileInfoBox Component**
   - Build a new `FileInfoBox.js` component that:
     - Fetches data from the `/api/files/netspeed_info` endpoint
     - Displays the file name, creation date, and line count
     - Handles loading and error states
     - Uses Material UI styling for consistent appearance

2. **App Integration**
   - Import and render the FileInfoBox component above the CSVSearch component in App.js

### Implementation
- The backend endpoint reads the netspeed.csv file stats and counts its lines
- The frontend component makes an API call and displays the information in a styled Paper component
- The component updates automatically when the page loads

### Acceptance Criteria
1. The FileInfoBox appears above the search field
2. It displays the current file name (netspeed.csv)
3. It shows the creation date of the file
4. It shows the number of lines/entries in the file
5. It handles cases where the file doesn't exist
6. It has appropriate loading and error states

## Task 0.1: CSV Table Column Order and Result Window Improvements

### Objective
Customize the CSV table to display specific columns in a defined order, add the source file name and creation date to each row, and make the result window expand to fit all results without scrollbars.

### Technical Requirements

#### Backend
1. **CSV Utility Changes**
   - The CSV utility now adds "File Name" and "Creation Date" to each row of data
   - Column order is defined with a specific sequence (IP Address, Line Number, MAC Address, etc.)

#### Frontend
1. **Column Ordering**
   - Modified `useFilePreview.js` and `useSearchCSV.js` to filter and order columns according to the specified sequence
   - The desired column order now includes "File Name" and "Creation Date" as the first two columns

2. **Improved Table Sizing with Horizontal Scrolling**
   - Removed fixed height constraints from the table container
   - Set `height: auto` and `maxHeight: none` to allow the table to expand to its full height vertically
   - Changed `overflow: visible` to `overflow: auto` to enable horizontal scrolling when needed
   - Used `width: auto` with `tableLayout: fixed` for better column sizing
   - Implemented `<colgroup>` with pixel-based minimum widths instead of percentages:
     - File Name: minWidth 120px
     - Creation Date: minWidth 150px
     - IP Address: minWidth 100px
     - Line Number: minWidth 100px
     - MAC Address: minWidth 130px
     - Subnet Mask: minWidth 100px
     - Voice VLAN: minWidth 80px
     - Switch Hostname: minWidth 150px
     - Switch Port: minWidth 150px
     - Serial Number: minWidth 120px
     - Model Name: minWidth 120px
   - Removed `stickyHeader` property which can cause scrolling behavior
   - Added a stronger box shadow for better visual appearance

3. **Dynamic Entry Count and User-Adjustable Preview Size**
   - Added a dropdown to let users select how many entries to preview (10, 25, 50, or 100)
   - Modified the `FilePreview` component to use React state for tracking the selected preview limit
   - Updated the heading to show the actual number of entries being displayed
   - Modified `useFilePreview` hook to get the total line count from the `netspeed_info` endpoint
   - Ensured all numerical values (preview count, total count) are dynamic and accurate
   - Created a responsive layout with the preview limit control placed next to the heading

### Implementation
- The backend API now attaches file name and creation date metadata to each row
- The frontend hooks filter and reorder the columns according to the desired order
- The table container styling has been modified to eliminate scrollbars and expand to fit all content

### Acceptance Criteria
1. The CSV table displays only the specified columns in the exact specified order
2. Each row displays the source file name and creation date as the first two columns
3. The result window expands to show all results without requiring internal scrolling
4. The table has an improved visual appearance with better shadows and spacing

## Task 0.2: Dark Mode Implementation

### Objective
Add a dark mode feature to the application to improve user experience in low-light environments and provide a modern UI option.

### Technical Requirements

#### Frontend

1. **Theme Configuration**
   - Created a `theme` folder with:
     - `theme.js`: Defines light and dark themes using MUI's `createTheme`
     - `ThemeContext.js`: Provides a theme context and custom hook for theme toggling
   - Themes include customized styles for:
     - Color palette (text, background, primary/secondary colors)
     - Table styling (rows, headers, backgrounds)
     - Component appearance (papers, app bar)

2. **Dark Mode Toggle**
   - Created a `DarkModeToggle.js` component with:
     - An icon button that toggles between sun (light mode) and moon (dark mode) icons
     - Integration with the ThemeContext for state management
     - Proper tooltips for accessibility

3. **Theme Provider Integration**
   - Added ThemeProvider to wrap the entire application
   - Implemented local storage persistence for user theme preference
   - Added system preference detection (prefers-color-scheme)

### Implementation
- The application uses React Context API to manage theme state
- Theme preferences are saved to localStorage for persistence between sessions
- The app respects the user's system preferences by default
- Components automatically adapt to theme changes without requiring refreshes
- Table styling maintains readability in both light and dark modes

### Acceptance Criteria
1. The application provides a dark mode toggle button in the header
2. Light and dark themes are properly applied to all components
3. User theme preference is persisted between sessions
4. The app respects system-level dark mode preference
5. All components remain fully functional and readable in both themes
6. Tables and data maintain proper contrast and readability in dark mode

## Task 1.1: Row Number Column Addition

### Objective
Add a "#" column to the CSV data display that shows sequential row numbers, making it easier to reference specific entries in the dataset.

### Technical Requirements

#### Backend
1. **CSV Utility Changes**
   - Modified the CSV utility to add a "#" column to each row
   - Added "#" to the DESIRED_ORDER list to ensure it appears as the first column
   - Row numbers start from 1 and increment sequentially

#### Frontend
1. **Column Display**
   - Updated `useFilePreview.js` to include the "#" column in the desired column order
   - The "#" column appears as the first column in the table
   - Numbers are displayed as strings to maintain consistency with other cell values

### Implementation
- The backend adds a "#" field to each row during CSV processing
- The frontend displays this field as the first column in the table
- Row numbers provide a clear reference point for each entry

### Acceptance Criteria
1. A "#" column appears as the first column in the CSV preview table
2. Each row displays its sequential number starting from 1
3. The numbering is consistent and accurate across all displayed rows

## Task 1: MAC Address Search Implementation

### Objective
Create a search functionality on the React website that allows users to search for MAC addresses. If a MAC address from the netspeed.csv files is present, it should display a CSV table with all the headers from the netspeed.csv file.

### Technical Requirements

#### Backend (FastAPI)

1. **Enhance Search API**
   - Modify the existing `/api/search` endpoint to handle MAC address queries
   - Add specific parameter for MAC address search 
   - Implement CSV parsing for netspeed files
   - Return complete row data if a match is found

2. **CSV Parsing Logic**
   - Create utility function to read and parse CSV files
   - Extract headers and data rows
   - Enable searching through multiple netspeed.csv files (current and historical)

#### Frontend (React)

1. **Create Search Component**
   - Build a `MacAddressSearch` component with:
     - Search input field with validation for MAC address format
     - Search button
     - Results display area

2. **Implement Results Table**
   - Create a table component that:
     - Displays all CSV headers as column headers
     - Shows the matching row data
     - Handles loading states and error messages
     - Provides appropriate feedback when no results are found

3. **API Integration**
   - Create a custom hook (`useSearchMacAddress`) to:
     - Make API calls to the backend search endpoint
     - Handle loading and error states
     - Format and return the search results

### Implementation Steps

1. **Backend**
   ```python
   # Sample code structure for backend implementation
   @router.get("/search")
   async def search_files(
       query: str = Query(None),
       mac_address: str = Query(None),
       include_historical: bool = Query(False)
   ):
       if mac_address:
           # Search for MAC address in CSV files
           result = await search_mac_address_in_files(mac_address, include_historical)
           return result
       # Existing search logic...
   ```

2. **Frontend**
   ```javascript
   // Sample code structure for frontend implementation
   function MacAddressSearch() {
     const [macAddress, setMacAddress] = useState('');
     const [searchResults, setSearchResults] = useState(null);
     
     const handleSearch = async () => {
       try {
         const response = await axios.get('/api/search', {
           params: {
             mac_address: macAddress,
             include_historical: true
           }
         });
         setSearchResults(response.data);
       } catch (error) {
         console.error('Error searching MAC address:', error);
       }
     };
     
     return (
       // Render search UI and results table
     );
   }
   ```

### Acceptance Criteria

1. Users can enter a MAC address in a search field and submit the search
2. The system validates the MAC address format
3. If a match is found, all data from the matching row is displayed in a table
4. The table includes all headers from the original CSV file
5. If no match is found, an appropriate message is displayed
6. The search works for both current and historical netspeed.csv files
