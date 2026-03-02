import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import Dashboard from './Dashboard';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  const renderDashboard = () => {
    return render(
      <BrowserRouter>
        <Dashboard />
      </BrowserRouter>
    );
  };

  it('renders empty state when no aides: shows "Nothing yet." and "Create your first aide" button', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ aides: [] }),
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText(/nothing yet/i)).toBeInTheDocument();
    });

    expect(screen.getByText(/create your first aide/i)).toBeInTheDocument();
  });

  it('renders aide cards when aides exist: title, status badge, last edited timestamp', async () => {
    const mockAides = [
      {
        id: 'aide1',
        title: 'Test Aide 1',
        is_published: true,
        updated_at: '2026-03-01T10:00:00Z',
      },
      {
        id: 'aide2',
        title: 'Test Aide 2',
        is_published: false,
        updated_at: '2026-03-01T11:00:00Z',
      },
    ];

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ aides: mockAides }),
    });

    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Test Aide 1')).toBeInTheDocument();
    });

    expect(screen.getByText('Test Aide 2')).toBeInTheDocument();
    expect(screen.getByText(/published/i)).toBeInTheDocument();
    expect(screen.getByText(/draft/i)).toBeInTheDocument();
  });

  it('"+" button calls create handler', async () => {
    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ aides: [] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: 'new-aide-123', title: 'Untitled' }),
      });

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /\+|create/i })).toBeInTheDocument();
    });

    const createButton = screen.getByRole('button', { name: /\+|create/i });
    await user.click(createButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/aides', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith('/a/new-aide-123');
  });

  it('clicking a card navigates to /a/{aide_id}', async () => {
    const mockAides = [
      {
        id: 'aide1',
        title: 'Test Aide',
        is_published: false,
        updated_at: '2026-03-01T10:00:00Z',
      },
    ];

    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ aides: mockAides }),
    });

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Test Aide')).toBeInTheDocument();
    });

    const card = screen.getByText('Test Aide').closest('.aide-card, [role="button"]');
    await user.click(card);

    expect(mockNavigate).toHaveBeenCalledWith('/a/aide1');
  });

  it('archive action shows confirm modal, calls API on confirm', async () => {
    const mockAides = [
      {
        id: 'aide1',
        title: 'Test Aide',
        is_published: false,
        updated_at: '2026-03-01T10:00:00Z',
      },
    ];

    global.fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ aides: mockAides }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.getByText('Test Aide')).toBeInTheDocument();
    });

    // Find and click archive button
    const archiveButton = screen.getByRole('button', { name: /archive/i });
    await user.click(archiveButton);

    // Confirm in modal
    await waitFor(() => {
      expect(screen.getByText(/confirm|sure/i)).toBeInTheDocument();
    });

    const confirmButton = screen.getByRole('button', { name: /confirm|yes/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith('/api/aides/aide1/archive', {
        method: 'POST',
      });
    });

    // Card should be removed from grid
    await waitFor(() => {
      expect(screen.queryByText('Test Aide')).not.toBeInTheDocument();
    });
  });
});
