import React from 'react';
import { Container, AppBar, Toolbar, Typography, Divider } from '@mui/material';
import FileTable from './components/FileTable';
import CSVSearch from './components/CSVSearch';
import FileInfoBox from './components/FileInfoBox';
import DarkModeToggle from './components/DarkModeToggle';

function App() {
  return (
    <div className="App">
      <AppBar position="static" sx={{ marginBottom: 2 }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            CSV Data Viewer
          </Typography>
          <DarkModeToggle />
        </Toolbar>
      </AppBar>
      <Container>
        <main>
          <Typography variant="h4" component="h1" gutterBottom>
            CSV Data Viewer
          </Typography>
          <Typography variant="body1" paragraph>
            View and search CSV files containing network data.
          </Typography>
          
          {/* File Info Box */}
          <FileInfoBox />
          
          {/* CSV Search */}
          <CSVSearch />
          
          <Divider sx={{ my: 4 }} />
          
          {/* File List */}
          <FileTable />
        </main>
      </Container>
    </div>
  );
}

export default App;
