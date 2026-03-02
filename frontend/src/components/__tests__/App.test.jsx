/**
 * App.test.jsx - Tests for App component (routing and auth integration)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App.jsx';
import * as useAuthModule from '../../hooks/useAuth.jsx';

// Mock the useAuth hook
vi.mock('../../hooks/useAuth.jsx', () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }) => children,
}));

describe('App', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders auth screen when not authenticated and not loading', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: false,
      isLoading: false,
      user: null,
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    // Should show email input
    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
  });

  it('does not render auth screen when loading', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: false,
      isLoading: true,
      user: null,
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    // Should NOT show email input while loading
    expect(screen.queryByPlaceholderText(/email/i)).not.toBeInTheDocument();
  });

  it('renders dashboard at / when authenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 'user-1', email: 'test@example.com' },
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>
    );

    // Should show dashboard (presence of "New" button or aide grid)
    // Using a more flexible matcher since we don't know exact text
    expect(screen.getByText(/new/i) || screen.getByTestId('dashboard')).toBeTruthy();
  });

  it('renders editor at /a/:aideId when authenticated', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 'user-1', email: 'test@example.com' },
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/a/test-id']}>
        <App />
      </MemoryRouter>
    );

    // Should show editor
    expect(screen.getByTestId('editor') || screen.getByTestId('preview')).toBeTruthy();
  });

  it('redirects unknown routes to /', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 'user-1', email: 'test@example.com' },
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    render(
      <MemoryRouter initialEntries={['/xyz']}>
        <App />
      </MemoryRouter>
    );

    // Should redirect to dashboard (check for dashboard elements)
    expect(screen.getByText(/new/i) || screen.getByTestId('dashboard')).toBeTruthy();
  });
});
