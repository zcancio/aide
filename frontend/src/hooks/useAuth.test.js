import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useAuth, AuthProvider } from './useAuth';

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it('returns { user: null, isAuthenticated: false } initially (no session cookie)', () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('on mount: calls GET /auth/me — if 200, sets user', async () => {
    const mockUser = { id: '123', email: 'test@example.com', tier: 'free' };
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockUser,
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(global.fetch).toHaveBeenCalledWith('/auth/me');
  });

  it('on mount: calls GET /auth/me — if 401, stays unauthenticated', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 401,
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalled();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it('sendMagicLink(email) calls POST /auth/send with { email }', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    });

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await result.current.sendMagicLink('test@example.com');

    expect(global.fetch).toHaveBeenCalledWith('/auth/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.com' }),
    });
  });

  it('verifyToken(token) calls GET /auth/verify?token={token}, sets user on success', async () => {
    const mockUser = { id: '123', email: 'test@example.com', tier: 'free' };
    global.fetch
      .mockResolvedValueOnce({ ok: false, status: 401 }) // Initial /auth/me
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      }); // /auth/verify

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await result.current.verifyToken('abc123');

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(global.fetch).toHaveBeenCalledWith('/auth/verify?token=abc123');
  });

  it('logout() calls POST /auth/logout, clears user state', async () => {
    const mockUser = { id: '123', email: 'test@example.com', tier: 'free' };
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      }) // Initial /auth/me
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      }); // /auth/logout

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await result.current.logout();

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(false);
    });

    expect(result.current.user).toBeNull();
    expect(global.fetch).toHaveBeenCalledWith('/auth/logout', {
      method: 'POST',
    });
  });

  it('after verify: { user: { id, email, tier }, isAuthenticated: true }', async () => {
    const mockUser = { id: '456', email: 'verified@example.com', tier: 'pro' };
    global.fetch
      .mockResolvedValueOnce({ ok: false, status: 401 }) // Initial /auth/me
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      }); // /auth/verify

    const { result } = renderHook(() => useAuth(), {
      wrapper: ({ children }) => <AuthProvider>{children}</AuthProvider>,
    });

    await result.current.verifyToken('token123');

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    expect(result.current.user).toEqual({
      id: '456',
      email: 'verified@example.com',
      tier: 'pro',
    });
  });
});
