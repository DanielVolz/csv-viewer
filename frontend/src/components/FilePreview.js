import React from 'react';
import CSVSearch from './CSVSearch';

/**
 * Component that displays a preview of the current netspeed CSV file
 */
function FilePreview() {
  const previewLimit = 100;

  return (
    <CSVSearch previewLimit={previewLimit} />
  );
}

export default FilePreview;
