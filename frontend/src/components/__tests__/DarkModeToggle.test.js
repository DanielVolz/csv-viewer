import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import DarkModeToggle from '../DarkModeToggle';
import { useTheme } from '../../theme/ThemeContext';

// Mock the useTheme hook
jest.mock('../../theme/ThemeContext');

describe('DarkModeToggle Component', () => {
  beforeEach(() => {
    // Reset the mock before each test
    useTheme.mockReset();
  });

  it('renders in light mode correctly', () => {
    // Mock useTheme to return light mode
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: jest.fn()
    });

    render(<DarkModeToggle />);

    // Check if the button is rendered
    const toggleButton = screen.getByRole('button', { name: /switch to dark mode/i });
    expect(toggleButton).toBeInTheDocument();

    // Check if the moon icon is displayed (for light mode)
    // We can't directly test for the icon component, but we can verify aria-label
    expect(toggleButton).toHaveAttribute('aria-label', 'Switch to dark mode');
  });

  it('renders in dark mode correctly', () => {
    // Mock useTheme to return dark mode
    useTheme.mockReturnValue({
      isDarkMode: true,
      toggleTheme: jest.fn()
    });

    render(<DarkModeToggle />);

    // Check if the button is rendered
    const toggleButton = screen.getByRole('button', { name: /switch to light mode/i });
    expect(toggleButton).toBeInTheDocument();

    // Check if the sun icon is displayed (for dark mode)
    expect(toggleButton).toHaveAttribute('aria-label', 'Switch to light mode');
  });

  it('calls toggleTheme when button is clicked', () => {
    // Create a mock function for toggleTheme
    const mockToggleTheme = jest.fn();

    // Mock useTheme to return the mock function
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: mockToggleTheme
    });

    render(<DarkModeToggle />);

    // Find the button and click it
    const toggleButton = screen.getByRole('button');
    fireEvent.click(toggleButton);

    // Check if toggleTheme was called
    expect(mockToggleTheme).toHaveBeenCalledTimes(1);
  });

  it('has the correct tooltip based on theme', () => {
    // Test light mode tooltip
    useTheme.mockReturnValue({
      isDarkMode: false,
      toggleTheme: jest.fn()
    });

    const { rerender } = render(<DarkModeToggle />);

    // Finding the tooltip is tricky in React Testing Library since it might be in a portal
    // Instead we test the aria-label which should match the tooltip
    let toggleButton = screen.getByRole('button');
    expect(toggleButton).toHaveAttribute('aria-label', 'Switch to dark mode');

    // Test dark mode tooltip by re-rendering with dark mode
    useTheme.mockReturnValue({
      isDarkMode: true,
      toggleTheme: jest.fn()
    });

    rerender(<DarkModeToggle />);

    toggleButton = screen.getByRole('button');
    expect(toggleButton).toHaveAttribute('aria-label', 'Switch to light mode');
  });
});
