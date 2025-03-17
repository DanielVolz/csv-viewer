import React from 'react';
import { Container, AppBar, Toolbar, Typography, CssBaseline, Divider } from '@mui/material';
import FileTable from './components/FileTable';
import MacAddressSearch from './components/MacAddressSearch';

function App() {
  return (
    <div className="App">
      <CssBaseline />
      <AppBar position="static" sx={{ marginBottom: 2 }}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            CSV Data Viewer
          </Typography>
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
          
          {/* MAC Address Search */}
          <MacAddressSearch />
          
          <Divider sx={{ my: 4 }} />
          
          {/* File List */}
          <Typography variant="h5" gutterBottom>
            Available Netspeed Files
          </Typography>
          <FileTable />
        </main>
      </Container>
    </div>
  );
}

export default App;
