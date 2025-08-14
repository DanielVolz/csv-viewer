import React from 'react';
import { Box, LinearProgress, Typography, Paper } from '@mui/material';

export default function IndexingProgress({ status, progress, result }) {
    if (status === 'idle' || (status === 'completed' && !result)) return null;

    // Completed
    if (status === 'completed') {
        return (
            <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Typography variant="subtitle2" gutterBottom>Indexing completed</Typography>
                <Typography variant="body2">Files: {result?.files_processed}</Typography>
                <Typography variant="body2">Documents: {result?.total_documents}</Typography>
            </Paper>
        );
    }

    // Error
    if (status === 'failed' || status === 'error') {
        return (
            <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
                <Typography variant="subtitle2" color="error">Indexing error</Typography>
                <Typography variant="body2">{progress?.error || 'See backend logs for details.'}</Typography>
            </Paper>
        );
    }

    // Running / Starting
    const total = progress?.total_files ?? 0;
    const current = progress?.index ?? 0;
    const haveTotal = total > 0;
    const startedFiles = current > 0;
    const percent = haveTotal ? (startedFiles ? Math.min(100, Math.round((current / total) * 100)) : 0) : 5;

    const fileLabel = haveTotal
        ? (startedFiles ? `File ${current} of ${total}` : `Preparing (0 of ${total})`)
        : 'Initializing...';
    const currentFileName = startedFiles ? progress?.current_file : '';

    return (
        <Paper sx={{ p: 2, mb: 2 }} elevation={1}>
            <Typography variant="subtitle2" gutterBottom>
                {status === 'starting' ? 'Starting indexing...' : 'Indexing in progress...'}
            </Typography>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                <Typography variant="caption">{fileLabel}</Typography>
                <Typography variant="caption">{currentFileName}</Typography>
            </Box>
            <LinearProgress variant="determinate" value={percent} sx={{ height: 6, borderRadius: 1 }} />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
                <Typography variant="caption">Total docs: {progress?.documents_indexed ?? 0}</Typography>
                {startedFiles && (
                    <Typography variant="caption">Last file: {progress?.last_file_docs ?? 0}</Typography>
                )}
            </Box>
        </Paper>
    );
}
