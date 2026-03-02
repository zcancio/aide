/**
 * Editor.test.jsx - Tests for Editor component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import Editor from '../Editor.jsx';
import * as useAideModule from '../../hooks/useAide.js';
import * as useWebSocketModule from '../../hooks/useWebSocket.js';

// Mock hooks
vi.mock('../../hooks/useAide.js', () => ({
  useAide: vi.fn(),
}));

vi.mock('../../hooks/useWebSocket.js', () => ({
  useWebSocket: vi.fn(),
}));

// Mock child components
vi.mock('../EditorHeader.jsx', () => ({
  default: () => <div data-testid="editor-header">Header</div>,
}));

vi.mock('../Preview.jsx', () => ({
  default: () => <div data-testid="preview">Preview</div>,
}));

vi.mock('../ChatOverlay.jsx', () => ({
  default: () => <div data-testid="chat-overlay">Chat</div>,
}));

describe('Editor', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default mock implementations
    vi.spyOn(useAideModule, 'useAide').mockReturnValue({
      entityStore: { entities: {}, rootIds: [], meta: {} },
      handleDelta: vi.fn(),
      handleSnapshot: vi.fn(),
      resetState: vi.fn(),
    });

    vi.spyOn(useWebSocketModule, 'useWebSocket').mockReturnValue({
      isConnected: true,
      send: vi.fn(),
      sendDirectEdit: vi.fn(),
    });
  });

  it('renders EditorHeader, Preview, and ChatOverlay', () => {
    render(
      <MemoryRouter initialEntries={['/a/test-aide-id']}>
        <Routes>
          <Route path="/a/:aideId" element={<Editor />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByTestId('editor-header')).toBeInTheDocument();
    expect(screen.getByTestId('preview')).toBeInTheDocument();
    expect(screen.getByTestId('chat-overlay')).toBeInTheDocument();
  });

  it('calls useAide hook on mount', () => {
    const mockUseAide = vi.spyOn(useAideModule, 'useAide');

    render(
      <MemoryRouter initialEntries={['/a/test-aide-id']}>
        <Routes>
          <Route path="/a/:aideId" element={<Editor />} />
        </Routes>
      </MemoryRouter>
    );

    expect(mockUseAide).toHaveBeenCalled();
  });

  it('calls useWebSocket with aideId from URL params', () => {
    const mockUseWebSocket = vi.spyOn(useWebSocketModule, 'useWebSocket');

    render(
      <MemoryRouter initialEntries={['/a/test-aide-id']}>
        <Routes>
          <Route path="/a/:aideId" element={<Editor />} />
        </Routes>
      </MemoryRouter>
    );

    expect(mockUseWebSocket).toHaveBeenCalledWith(
      'test-aide-id',
      expect.any(Object)
    );
  });
});
