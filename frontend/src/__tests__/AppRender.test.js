import React from 'react';
import { render, screen } from '@testing-library/react';
import App from '../App';

jest.mock('../components/Navigation', () => (props) => (
    <div data-testid="nav" data-current={props.currentTab || ''} />
));

// Prevent long-running effects and network calls during this smoke test
jest.mock('../components/FileInfoBox', () => () => (
    <div data-testid="file-info-box" />
));
jest.mock('../components/CSVSearch', () => () => (
    <div data-testid="csv-search" />
));
jest.mock('../hooks/useUpdateNotifier', () => () => { });

// Stub SettingsProvider to avoid axios calls/useColumns side-effects in this smoke test
jest.mock('../contexts/SettingsContext', () => {
    const React = require('react');
    return {
        SettingsProvider: ({ children }) => <>{children}</>,
        useSettings: () => ({ setNavigationFunction: () => { } })
    };
});

// Light smoke test that App renders main layout without crashing
it('renders app root', () => {
    render(<App />);
    expect(screen.getByTestId('nav')).toBeInTheDocument();
});
