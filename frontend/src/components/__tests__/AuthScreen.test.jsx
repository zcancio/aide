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
    mockSearchParams.delete('token');
  });

  it('renders email input and send button', () => {
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
      verifyToken: vi.fn(),
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
      verifyToken: vi.fn(),
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
      verifyToken: vi.fn(),
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

  it('calls verifyToken on mount when token is in URL', async () => {
    mockSearchParams.set('token', 'test-token-123');
    const mockVerifyToken = vi.fn().mockResolvedValue({ data: {} });
    vi.spyOn(useAuthModule, 'useAuth').mockReturnValue({
      sendMagicLink: vi.fn(),
      verifyToken: mockVerifyToken,
    });

    render(
      <MemoryRouter initialEntries={['/?token=test-token-123']}>
        <AuthScreen />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(mockVerifyToken).toHaveBeenCalledWith('test-token-123');
    });
  });
});
