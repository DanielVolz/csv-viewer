# Implementation Tasks

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
