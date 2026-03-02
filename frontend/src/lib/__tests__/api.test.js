import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  fetchAides,
  fetchAide,
  createAide,
  updateAide,
  archiveAide,
  deleteAide,
  sendMessage,
  publishAide,
  unpublishAide,
  sendMagicLink,
  verifyToken,
  fetchMe,
  logout,
} from '../api.js';

describe('api', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('fetchAides() calls GET /api/aides and returns data on 200', async () => {
    const mockData = [{ id: 'a1', title: 'Test' }];
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await fetchAides();

    expect(global.fetch).toHaveBeenCalledWith('/api/aides', {
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it("fetchAide('abc') calls GET /api/aides/abc", async () => {
    const mockData = { id: 'abc', title: 'Test' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await fetchAide('abc');

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc', {
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it('createAide() calls POST /api/aides', async () => {
    const mockData = { id: 'new', title: 'Untitled' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await createAide({ title: 'Untitled' });

    expect(global.fetch).toHaveBeenCalledWith('/api/aides', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Untitled' }),
    });
    expect(result).toEqual({ data: mockData });
  });

  it("updateAide('abc', { title: 'New' }) calls PATCH /api/aides/abc with body", async () => {
    const mockData = { id: 'abc', title: 'New' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await updateAide('abc', { title: 'New' });

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc', {
      method: 'PATCH',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'New' }),
    });
    expect(result).toEqual({ data: mockData });
  });

  it("archiveAide('abc') calls POST /api/aides/abc/archive", async () => {
    const mockData = { id: 'abc', status: 'archived' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await archiveAide('abc');

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc/archive', {
      method: 'POST',
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it("deleteAide('abc') calls DELETE /api/aides/abc", async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 204,
      json: async () => ({}),
    });

    const result = await deleteAide('abc');

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc', {
      method: 'DELETE',
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: {} });
  });

  it("sendMessage({ aide_id: 'abc', message: 'hi' }) calls POST /api/message with JSON body", async () => {
    const mockData = { aide_id: 'abc', response_text: 'hello' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await sendMessage({ aide_id: 'abc', message: 'hi' });

    expect(global.fetch).toHaveBeenCalledWith('/api/message', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ aide_id: 'abc', message: 'hi' }),
    });
    expect(result).toEqual({ data: mockData });
  });

  it("publishAide('abc', 'my-slug') calls POST /api/aides/abc/publish with slug", async () => {
    const mockData = { id: 'abc', slug: 'my-slug' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await publishAide('abc', 'my-slug');

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc/publish', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug: 'my-slug' }),
    });
    expect(result).toEqual({ data: mockData });
  });

  it("unpublishAide('abc') calls POST /api/aides/abc/unpublish", async () => {
    const mockData = { id: 'abc', status: 'draft' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await unpublishAide('abc');

    expect(global.fetch).toHaveBeenCalledWith('/api/aides/abc/unpublish', {
      method: 'POST',
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it("sendMagicLink('a@b.com') calls POST /auth/send with email", async () => {
    const mockData = { message: 'sent' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await sendMagicLink('a@b.com');

    expect(global.fetch).toHaveBeenCalledWith('/auth/send', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'a@b.com' }),
    });
    expect(result).toEqual({ data: mockData });
  });

  it("verifyToken('tok123') calls GET /auth/verify?token=tok123", async () => {
    const mockData = { user_id: 'u1' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await verifyToken('tok123');

    expect(global.fetch).toHaveBeenCalledWith('/auth/verify?token=tok123', {
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it('fetchMe() calls GET /auth/me', async () => {
    const mockData = { id: 'u1', email: 'a@b.com' };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await fetchMe();

    expect(global.fetch).toHaveBeenCalledWith('/auth/me', {
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: mockData });
  });

  it('logout() calls POST /auth/logout', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });

    const result = await logout();

    expect(global.fetch).toHaveBeenCalledWith('/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });
    expect(result).toEqual({ data: {} });
  });

  it('returns { data } on HTTP 200', async () => {
    const mockData = { success: true };
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await fetchMe();
    expect(result).toEqual({ data: mockData });
  });

  it('returns { error } on HTTP 4xx with detail', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Invalid request' }),
    });

    const result = await fetchMe();
    expect(result).toEqual({ error: 'Invalid request' });
  });

  it('returns { error } on HTTP 5xx with statusText', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
      json: async () => ({}),
    });

    const result = await fetchMe();
    expect(result).toEqual({ error: 'Internal Server Error' });
  });

  it('includes credentials: same-origin in every request', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({}),
    });

    await fetchAides();
    await fetchMe();
    await createAide({ title: 'Test' });

    const calls = global.fetch.mock.calls;
    calls.forEach((call) => {
      const options = call[1];
      expect(options.credentials).toBe('same-origin');
    });
  });
});
