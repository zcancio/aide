/**
 * App.test.jsx - Tests for App component (routing and auth integration)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import App from '../App.jsx';
import * as useAuthModule from '../../hooks/useAuth.jsx';

// Mock the entire useAuth hook
vi.mock('../../hooks/useAuth.jsx', () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }) => children, // Pass through
}));

// Mock child components to simplify tests
vi.mock('../AuthScreen.jsx', () => ({
  default: () => <div><input placeholder="Your email" /></div>,
}));

vi.mock('../Dashboard.jsx', () => ({
  default: () => <div data-testid="dashboard">Dashboard<button>New</button></div>,
}));

vi.mock('../Editor.jsx', () => ({
  default: () => <div data-testid="editor"><div data-testid="preview">Preview</div></div>,
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

    render(<App />);

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

    render(<App />);

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

    // Set initial location to /
    window.history.pushState({}, 'Test', '/');

    render(<App />);

    // Should show dashboard
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
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

    // Set initial location to /a/test-id
    window.history.pushState({}, 'Test', '/a/test-id');

    render(<App />);

    // Should show editor
    expect(screen.getByTestId('editor')).toBeInTheDocument();
  });

  it('redirects unknown routes to /', async () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      isAuthenticated: true,
      isLoading: false,
      user: { id: 'user-1', email: 'test@example.com' },
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
      logout: vi.fn(),
    });

    // Set initial location to unknown route
    window.history.pushState({}, 'Test', '/xyz');

    render(<App />);

    // Should redirect to dashboard
    expect(screen.getByTestId('dashboard')).toBeInTheDocument();
  });
});
