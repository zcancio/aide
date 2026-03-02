/**
 * Tests for useAuth hook
 * Tests auth state management, loading states, and auth operations
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../useAuth.js';
import * as api from '../../lib/api.js';

vi.mock('../../lib/api.js');

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns initial state with loading=true, user=null, isAuthenticated=false', () => {
    api.fetchMe.mockResolvedValue({ data: null });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    expect(result.current.user).toBe(null);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(true);
  });

  it('sets user and isAuthenticated=true when fetchMe returns user data', async () => {
    const mockUser = { id: '1', email: 'a@b.com' };
    api.fetchMe.mockResolvedValue({ data: mockUser });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('sets user=null and isAuthenticated=false when fetchMe returns error', async () => {
    api.fetchMe.mockResolvedValue({ error: 'Not authenticated' });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.user).toBe(null);
    expect(result.current.isAuthenticated).toBe(false);
  });

  it('sendMagicLink calls api.sendMagicLink with email', async () => {
    api.fetchMe.mockResolvedValue({ error: 'Not authenticated' });
    api.sendMagicLink.mockResolvedValue({ data: { success: true } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const email = 'a@b.com';
    await act(async () => {
      await result.current.sendMagicLink(email);
    });

    expect(api.sendMagicLink).toHaveBeenCalledWith(email);
  });

  it('verifyToken calls api.verifyToken, sets user and isAuthenticated on success', async () => {
    const mockUser = { id: '2', email: 'verified@example.com' };
    api.fetchMe.mockResolvedValue({ error: 'Not authenticated' });
    api.verifyToken.mockResolvedValue({ data: mockUser });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    const token = 'test-token';
    await act(async () => {
      await result.current.verifyToken(token);
    });

    expect(api.verifyToken).toHaveBeenCalledWith(token);
    expect(result.current.user).toEqual(mockUser);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it('logout calls api.logout, sets user=null and isAuthenticated=false', async () => {
    const mockUser = { id: '1', email: 'a@b.com' };
    api.fetchMe.mockResolvedValue({ data: mockUser });
    api.logout.mockResolvedValue({ data: { success: true } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isAuthenticated).toBe(true);
    });

    await act(async () => {
      await result.current.logout();
    });

    expect(api.logout).toHaveBeenCalled();
    expect(result.current.user).toBe(null);
    expect(result.current.isAuthenticated).toBe(false);
  });
});
