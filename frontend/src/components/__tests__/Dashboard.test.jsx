/**
 * Dashboard.test.jsx - Tests for Dashboard component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Dashboard from '../Dashboard.jsx';
import * as api from '../../lib/api.js';

// Mock API
vi.mock('../../lib/api.js', () => ({
  fetchAides: vi.fn(),
  createAide: vi.fn(),
}));

// Mock useNavigate
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
  });

  it('shows empty state when no aides', async () => {
    vi.spyOn(api, 'fetchAides').mockResolvedValue({ data: [] });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/nothing yet/i)).toBeInTheDocument();
      expect(screen.getByText(/create your first aide/i)).toBeInTheDocument();
    });
  });

  it('renders aide cards when aides exist', async () => {
    vi.spyOn(api, 'fetchAides').mockResolvedValue({
      data: [
        { id: 'aide-1', title: 'First Aide', updated_at: '2026-01-01' },
        { id: 'aide-2', title: 'Second Aide', updated_at: '2026-01-02' },
      ],
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('First Aide')).toBeInTheDocument();
      expect(screen.getByText('Second Aide')).toBeInTheDocument();
    });
  });

  it('creates aide and navigates when + button is clicked', async () => {
    vi.spyOn(api, 'fetchAides').mockResolvedValue({ data: [] });
    vi.spyOn(api, 'createAide').mockResolvedValue({ data: { id: 'new-aide-id' } });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/nothing yet/i)).toBeInTheDocument();
    });

    const newButton = screen.getByRole('button', { name: /new/i }) || screen.getByText(/\+/);
    fireEvent.click(newButton);

    await waitFor(() => {
      expect(api.createAide).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith('/a/new-aide-id');
    });
  });

  it('navigates to aide when card is clicked', async () => {
    vi.spyOn(api, 'fetchAides').mockResolvedValue({
      data: [{ id: 'aide-1', title: 'Test Aide', updated_at: '2026-01-01' }],
    });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Test Aide')).toBeInTheDocument();
    });

    const card = screen.getByText('Test Aide').closest('[data-aide-id]') || screen.getByText('Test Aide');
    fireEvent.click(card);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/a/aide-1');
    });
  });
});
