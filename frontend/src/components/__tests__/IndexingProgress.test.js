import React from 'react';
import { render, screen } from '@testing-library/react';
import IndexingProgress from '../IndexingProgress';

const makeProgress = (over = {}) => ({
    total_files: 3,
    index: 1,
    current_file: 'netspeed.csv',
    documents_indexed: 100,
    last_file_docs: 100,
    ...over
});

test('renders nothing when idle', () => {
    const { container } = render(<IndexingProgress status="idle" />);
    expect(container.firstChild).toBeNull();
});

test('renders completed summary', () => {
    render(<IndexingProgress status="completed" result={{ files_processed: 5, total_documents: 1234 }} />);
    expect(screen.getByText(/Indexing completed/i)).toBeInTheDocument();
    expect(screen.getByText(/Files: 5/i)).toBeInTheDocument();
    expect(screen.getByText(/Documents: 1234/i)).toBeInTheDocument();
});

test('renders error state', () => {
    render(<IndexingProgress status="failed" progress={{ error: 'boom' }} />);
    expect(screen.getByText(/Indexing error/i)).toBeInTheDocument();
    expect(screen.getByText(/boom/i)).toBeInTheDocument();
});

test('renders running with percent and labels', () => {
    render(<IndexingProgress status="running" progress={makeProgress()} />);
    expect(screen.getByText(/Indexing in progress/i)).toBeInTheDocument();
    expect(screen.getByText(/File 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByText(/netspeed.csv/i)).toBeInTheDocument();
    expect(screen.getByText(/Total docs: 100/i)).toBeInTheDocument();
    expect(screen.getByText(/Last file: 100/i)).toBeInTheDocument();
});
