/**
 * Preview.test.jsx - Tests for Preview component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import Preview from '../Preview.jsx';

// Mock display library
const mockRenderHtml = vi.fn();
vi.mock('../../../display.js', () => ({
  renderHtml: (store) => mockRenderHtml(store),
  RENDERER_CSS: '/* mock css */',
}));

describe('Preview', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRenderHtml.mockReturnValue('<div class="aide-page">Test content</div>');
  });

  it('renders a div with class aide-preview', () => {
    const entityStore = { entities: {}, rootIds: [], meta: {} };

    render(<Preview entityStore={entityStore} onDirectEdit={vi.fn()} />);

    const preview = screen.getByTestId('preview') || document.querySelector('.aide-preview');
    expect(preview).toBeInTheDocument();
  });

  it('renders HTML from entityStore when entities exist', () => {
    const entityStore = {
      entities: { 'e1': { id: 'e1', props: { title: 'Test' } } },
      rootIds: ['e1'],
      meta: { title: 'Test Page' },
    };
    mockRenderHtml.mockReturnValue('<div class="aide-page">Rendered content</div>');

    render(<Preview entityStore={entityStore} onDirectEdit={vi.fn()} />);

    // Should contain rendered HTML
    const preview = screen.getByTestId('preview') || document.querySelector('.aide-preview');
    expect(preview.innerHTML).toContain('aide-page');
  });

  it('shows empty state when entityStore is empty', () => {
    const entityStore = { entities: {}, rootIds: [], meta: {} };
    mockRenderHtml.mockReturnValue('<div class="aide-page"><p class="aide-empty">Send a message to get started.</p></div>');

    render(<Preview entityStore={entityStore} onDirectEdit={vi.fn()} />);

    expect(screen.getByText(/send a message to get started/i) || screen.getByText(/empty/i)).toBeInTheDocument();
  });
});
