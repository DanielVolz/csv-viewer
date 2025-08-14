import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import Navigation from '../Navigation';

it('calls onHomeClick when clicking the Search tab', () => {
    const onHomeClick = jest.fn();
    const onTabChange = jest.fn();
    render(<Navigation currentTab="home" onHomeClick={onHomeClick} onTabChange={onTabChange} />);

    const searchTab = screen.getByRole('tab', { name: /Search/i });
    fireEvent.click(searchTab);
    expect(onHomeClick).toHaveBeenCalled();
});
