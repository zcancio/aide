/**
 * AuthScreen.test.jsx - Tests for AuthScreen component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AuthScreen from '../AuthScreen.jsx';
import * as useAuthModule from '../../hooks/useAuth.jsx';

// Mock useAuth
vi.mock('../../hooks/useAuth.jsx', () => ({
  useAuth: vi.fn(),
}));

// Mock useSearchParams
const mockSearchParams = new URLSearchParams();
const mockSetSearchParams = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useSearchParams: () => [mockSearchParams, mockSetSearchParams],
  };
});

describe('AuthScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.delete('error');
  });

  it('renders email input and send button', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send magic link/i })).toBeInTheDocument();
  });

  it('calls sendMagicLink when form is submitted', async () => {
    const mockSendMagicLink = vi.fn().mockResolvedValue({ data: {} });
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: mockSendMagicLink,
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    const emailInput = screen.getByPlaceholderText(/email/i);
    const sendButton = screen.getByRole('button', { name: /send magic link/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(mockSendMagicLink).toHaveBeenCalledWith('test@example.com');
    });
  });

  it('shows confirmation message after sending', async () => {
    const mockSendMagicLink = vi.fn().mockResolvedValue({ data: {} });
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: mockSendMagicLink,
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    const emailInput = screen.getByPlaceholderText(/email/i);
    const sendButton = screen.getByRole('button', { name: /send magic link/i });

    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });
  });

  it('displays error for invalid_link error param', () => {
    mockSearchParams.set('error', 'invalid_link');
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByText(/invalid magic link/i)).toBeInTheDocument();
  });

  it('displays error for link_used error param', () => {
    mockSearchParams.set('error', 'link_used');
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByText(/already been used/i)).toBeInTheDocument();
  });

  it('displays error for link_expired error param', () => {
    mockSearchParams.set('error', 'link_expired');
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByText(/expired/i)).toBeInTheDocument();
  });

  it('displays error for too_many_attempts error param', () => {
    mockSearchParams.set('error', 'too_many_attempts');
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByText(/too many/i)).toBeInTheDocument();
  });

  it('displays generic error for unknown error param', () => {
    mockSearchParams.set('error', 'unknown_error');
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
    });

    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>
    );

    expect(screen.getByText(/authentication failed/i)).toBeInTheDocument();
  });
});
