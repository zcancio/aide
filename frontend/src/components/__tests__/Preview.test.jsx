/**
 * Preview.test.jsx - Tests for Preview component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import Preview from '../Preview.jsx';

describe('Preview', () => {
  it('renders a div with class aide-preview', () => {
    const entityStore = { entities: {}, rootIds: [], meta: {} };

    render(<Preview entityStore={entityStore} onDirectEdit={() => {}} />);

    const preview = screen.getByTestId('preview');
    expect(preview).toBeInTheDocument();
    expect(preview).toHaveClass('aide-preview');
  });

  it('renders HTML from entityStore when entities exist', () => {
    const entityStore = {
      entities: { 'e1': { id: 'e1', props: { title: 'Test' } } },
      rootIds: ['e1'],
      meta: { title: 'Test Page' },
    };

    render(<Preview entityStore={entityStore} onDirectEdit={() => {}} />);

    const preview = screen.getByTestId('preview');
    expect(preview).toBeInTheDocument();

    // Shadow DOM should be created
    expect(preview.shadowRoot).toBeTruthy();
  });

  it('shows empty state when entityStore is empty', () => {
    const entityStore = { entities: {}, rootIds: [], meta: {} };

    render(<Preview entityStore={entityStore} onDirectEdit={() => {}} />);

    const preview = screen.getByTestId('preview');
    expect(preview).toBeInTheDocument();

    // Shadow DOM should be created
    expect(preview.shadowRoot).toBeTruthy();
  });
});
