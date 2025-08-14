import React from 'react';
import { render, screen } from '@testing-library/react';
import HomePage from '../HomePage';

jest.mock('../../components/FileInfoBox', () => () => <div data-testid="file-info-box" />);
jest.mock('../../components/CSVSearch', () => () => <div data-testid="csv-search" />);

it('renders FileInfoBox and CSVSearch', () => {
    render(<HomePage />);
    expect(screen.getByTestId('file-info-box')).toBeInTheDocument();
    expect(screen.getByTestId('csv-search')).toBeInTheDocument();
});
