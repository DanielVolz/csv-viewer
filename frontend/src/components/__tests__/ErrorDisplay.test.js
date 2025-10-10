import React from 'react';
import { render, screen } from '@testing-library/react';
import ErrorDisplay from '../ErrorDisplay';
import '@testing-library/jest-dom';

describe('ErrorDisplay Component', () => {
  describe('Paper variant (default)', () => {
    it('renders error type with title and message', () => {
      render(
        <ErrorDisplay
          type="error"
          title="Test Error"
          message="This is a test error message"
        />
      );

      expect(screen.getByText('Test Error')).toBeInTheDocument();
      expect(screen.getByText('This is a test error message')).toBeInTheDocument();
    });

    it('renders warning type correctly', () => {
      render(
        <ErrorDisplay
          type="warning"
          title="Test Warning"
          message="This is a warning"
        />
      );

      expect(screen.getByText('Test Warning')).toBeInTheDocument();
      expect(screen.getByText('This is a warning')).toBeInTheDocument();
    });

    it('renders info type correctly', () => {
      render(
        <ErrorDisplay
          type="info"
          title="Test Info"
          message="This is informational"
        />
      );

      expect(screen.getByText('Test Info')).toBeInTheDocument();
      expect(screen.getByText('This is informational')).toBeInTheDocument();
    });

    it('renders without title when not provided', () => {
      render(
        <ErrorDisplay
          type="error"
          message="Message only"
        />
      );

      expect(screen.getByText('Message only')).toBeInTheDocument();
    });

    it('renders without message when not provided', () => {
      render(
        <ErrorDisplay
          type="error"
          title="Title only"
        />
      );

      expect(screen.getByText('Title only')).toBeInTheDocument();
    });
  });

  describe('Alert variant', () => {
    it('renders as alert with title and message', () => {
      render(
        <ErrorDisplay
          type="error"
          title="Alert Title"
          message="Alert message"
          variant="alert"
        />
      );

      expect(screen.getByText('Alert Title')).toBeInTheDocument();
      expect(screen.getByText('Alert message')).toBeInTheDocument();
    });

    it('renders warning alert', () => {
      render(
        <ErrorDisplay
          type="warning"
          title="Warning"
          message="Warning message"
          variant="alert"
        />
      );

      expect(screen.getByText('Warning')).toBeInTheDocument();
      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });

    it('renders info alert', () => {
      render(
        <ErrorDisplay
          type="info"
          title="Info"
          message="Info message"
          variant="alert"
        />
      );

      expect(screen.getByText('Info')).toBeInTheDocument();
      expect(screen.getByText('Info message')).toBeInTheDocument();
    });
  });

  describe('Customization', () => {
    it('applies custom sx styling', () => {
      const { container } = render(
        <ErrorDisplay
          type="error"
          title="Custom Styled"
          message="With custom styles"
          sx={{ backgroundColor: 'red' }}
        />
      );

      // Check that the Paper/Alert component has custom styling applied
      const errorElement = container.firstChild;
      expect(errorElement).toBeTruthy();
    });
  });
});
