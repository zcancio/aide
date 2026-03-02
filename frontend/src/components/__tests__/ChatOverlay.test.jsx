/**
 * ChatOverlay.test.jsx - Tests for ChatOverlay component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatOverlay from '../ChatOverlay.jsx';

describe('ChatOverlay', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts in input state by default', () => {
    render(<ChatOverlay messages={[]} onSend={vi.fn()} />);

    // Should be in input state
    const overlay = screen.getByTestId('chat-overlay');
    expect(overlay).toHaveAttribute('data-state', 'input');

    // Input bar should be rendered (even if CSS hides it in hidden state)
    expect(screen.getByPlaceholderText(/message/i)).toBeInTheDocument();
  });

  it('expands to show history when handle is clicked', async () => {
    render(<ChatOverlay messages={[{ role: 'user', content: 'Test' }]} onSend={vi.fn()} />);

    const overlay = screen.getByTestId('chat-overlay');
    expect(overlay).toHaveAttribute('data-state', 'input');

    const handle = screen.getByTestId('chat-handle');
    fireEvent.click(handle);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'expanded');
    });
  });

  it('shows message history in expanded state', async () => {
    const messages = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
    ];

    render(<ChatOverlay messages={messages} onSend={vi.fn()} />);

    const overlay = screen.getByTestId('chat-overlay');

    // Expand by clicking handle
    const handle = screen.getByTestId('chat-handle');
    fireEvent.click(handle);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'expanded');
      expect(screen.getByText('Hello')).toBeInTheDocument();
      expect(screen.getByText('Hi there')).toBeInTheDocument();
    });
  });

  it('collapses from expanded to input on swipe down', async () => {
    render(<ChatOverlay messages={[{ role: 'user', content: 'Test' }]} onSend={vi.fn()} />);

    const overlay = screen.getByTestId('chat-overlay');

    // Expand first by clicking handle
    const handle = screen.getByTestId('chat-handle');
    fireEvent.click(handle);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'expanded');
    });

    // Simulate swipe down
    fireEvent.touchStart(overlay, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(overlay, { touches: [{ clientY: 200 }] }); // +100px = swipe down
    fireEvent.touchEnd(overlay);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'input');
    });
  });

  it('hides from input to hidden on swipe down', async () => {
    render(<ChatOverlay messages={[]} onSend={vi.fn()} />);

    const overlay = screen.getByTestId('chat-overlay');
    expect(overlay).toHaveAttribute('data-state', 'input');

    // Swipe down from input state
    fireEvent.touchStart(overlay, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(overlay, { touches: [{ clientY: 200 }] });
    fireEvent.touchEnd(overlay);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'hidden');
    });
  });

  it('opens from hidden to input on swipe up', async () => {
    render(<ChatOverlay messages={[]} onSend={vi.fn()} initialState="hidden" />);

    const overlay = screen.getByTestId('chat-overlay');
    expect(overlay).toHaveAttribute('data-state', 'hidden');

    // Swipe up
    fireEvent.touchStart(overlay, { touches: [{ clientY: 200 }] });
    fireEvent.touchMove(overlay, { touches: [{ clientY: 100 }] }); // -100px = swipe up
    fireEvent.touchEnd(overlay);

    await waitFor(() => {
      expect(overlay).toHaveAttribute('data-state', 'input');
    });
  });

  it('calls onSend when message is submitted', async () => {
    const mockOnSend = vi.fn();
    render(<ChatOverlay messages={[]} onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText(/message/i);
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(mockOnSend).toHaveBeenCalledWith('Test message');
    });
  });

  it('does not send on Shift+Enter, adds newline instead', async () => {
    const mockOnSend = vi.fn();
    render(<ChatOverlay messages={[]} onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText(/message/i);
    fireEvent.change(input, { target: { value: 'Line 1' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true });

    // Should NOT send
    expect(mockOnSend).not.toHaveBeenCalled();
  });
});
