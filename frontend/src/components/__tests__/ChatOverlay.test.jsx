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

    // Input bar should be visible
    expect(screen.getByPlaceholderText(/message/i) || screen.getByRole('textbox')).toBeInTheDocument();

    // Message history should NOT be visible initially
    const messages = screen.queryByTestId('message-history');
    if (messages) {
      expect(messages).not.toBeVisible();
    }
  });

  it('expands to show history when handle is clicked', async () => {
    render(<ChatOverlay messages={[{ role: 'user', content: 'Test' }]} onSend={vi.fn()} />);

    const handle = screen.getByTestId('chat-handle') || screen.getByText(/pull up/i) || screen.getByRole('button');
    fireEvent.click(handle);

    await waitFor(() => {
      const history = screen.getByTestId('message-history') || screen.getByText('Test');
      expect(history).toBeVisible();
    });
  });

  it('shows message history in expanded state', async () => {
    const messages = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
    ];

    render(<ChatOverlay messages={messages} onSend={vi.fn()} />);

    // Expand
    const handle = screen.getByTestId('chat-handle') || screen.getByRole('button');
    fireEvent.click(handle);

    await waitFor(() => {
      expect(screen.getByText('Hello')).toBeInTheDocument();
      expect(screen.getByText('Hi there')).toBeInTheDocument();
    });
  });

  it('collapses from expanded to input on swipe down', async () => {
    render(<ChatOverlay messages={[{ role: 'user', content: 'Test' }]} onSend={vi.fn()} />);

    // Expand first
    const handle = screen.getByTestId('chat-handle') || screen.getByRole('button');
    fireEvent.click(handle);

    await waitFor(() => {
      expect(screen.getByText('Test')).toBeVisible();
    });

    // Simulate swipe down
    const overlay = screen.getByTestId('chat-overlay') || screen.getByText('Test').closest('[data-state]');
    fireEvent.touchStart(overlay, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(overlay, { touches: [{ clientY: 200 }] });
    fireEvent.touchEnd(overlay);

    await waitFor(() => {
      const history = screen.queryByTestId('message-history');
      if (history) {
        expect(history).not.toBeVisible();
      }
    });
  });

  it('hides from input to hidden on swipe down', async () => {
    render(<ChatOverlay messages={[]} onSend={vi.fn()} />);

    const overlay = screen.getByTestId('chat-overlay') || screen.getByRole('textbox').closest('[data-state]');

    // Swipe down from input state
    fireEvent.touchStart(overlay, { touches: [{ clientY: 100 }] });
    fireEvent.touchMove(overlay, { touches: [{ clientY: 200 }] });
    fireEvent.touchEnd(overlay);

    await waitFor(() => {
      // Input should be hidden, only handle visible
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  it('opens from hidden to input on swipe up', async () => {
    render(<ChatOverlay messages={[]} onSend={vi.fn()} initialState="hidden" />);

    const handle = screen.getByTestId('chat-handle') || screen.getByRole('button');

    // Swipe up
    fireEvent.touchStart(handle, { touches: [{ clientY: 200 }] });
    fireEvent.touchMove(handle, { touches: [{ clientY: 100 }] });
    fireEvent.touchEnd(handle);

    await waitFor(() => {
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });
  });

  it('calls onSend when message is submitted', async () => {
    const mockOnSend = vi.fn();
    render(<ChatOverlay messages={[]} onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText(/message/i) || screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });

    await waitFor(() => {
      expect(mockOnSend).toHaveBeenCalledWith('Test message');
    });
  });

  it('does not send on Shift+Enter, adds newline instead', async () => {
    const mockOnSend = vi.fn();
    render(<ChatOverlay messages={[]} onSend={mockOnSend} />);

    const input = screen.getByPlaceholderText(/message/i) || screen.getByRole('textbox');
    fireEvent.change(input, { target: { value: 'Line 1' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter', shiftKey: true });

    // Should NOT send
    expect(mockOnSend).not.toHaveBeenCalled();
  });
});
