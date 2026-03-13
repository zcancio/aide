/**
 * Tests for useAuth hook
 * Tests auth state management, loading states, and auth operations
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../useAuth.jsx';
import * as api from '../../lib/api.js';
import * as fingerprint from '../../lib/fingerprint.js';

vi.mock('../../lib/api.js');
vi.mock('../../lib/fingerprint.js');

describe('useAuth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock for fingerprint
    fingerprint.getFingerprint.mockReturnValue('test-fingerprint-id');
    // Default mock for createShadowSession (returns error by default)
    api.createShadowSession.mockResolvedValue({ error: 'Not mocked' });
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

  it('creates shadow user when fetchMe returns error', async () => {
    const mockShadowUser = { id: 'shadow-1', email: null, is_shadow: true };
    api.fetchMe
      .mockResolvedValueOnce({ error: 'Not authenticated' })
      .mockResolvedValueOnce({ data: mockShadowUser });
    api.createShadowSession.mockResolvedValue({ data: { user_id: 'shadow-1' } });

    const { result } = renderHook(() => useAuth(), {
      wrapper: AuthProvider,
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.createShadowSession).toHaveBeenCalledWith('test-fingerprint-id');
    expect(result.current.user).toEqual(mockShadowUser);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.isShadow).toBe(true);
  });

  it('sets user=null when shadow session creation fails', async () => {
    api.fetchMe.mockResolvedValue({ error: 'Not authenticated' });
    api.createShadowSession.mockResolvedValue({ error: 'Failed' });

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
    const mockUser = { id: '1', email: 'a@b.com' };
    api.fetchMe.mockResolvedValue({ data: mockUser });
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
