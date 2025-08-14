import React from 'react';
import { render, screen } from '@testing-library/react';
import App from '../App';

jest.mock('../components/Navigation', () => (props) => (
    <div data-testid="nav" data-current={props.currentTab || ''} />
));

// Light smoke test that App renders main layout without crashing
it('renders app root', () => {
    render(<App />);
    expect(screen.getByTestId('nav')).toBeInTheDocument();
});
