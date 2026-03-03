/**
 * DemoPatterns.test.jsx - Tests for DemoPatterns component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import DemoPatterns from '../DemoPatterns.jsx';
import { getDemoEntityTree } from '../../lib/display/demo-entity-tree.js';

describe('DemoPatterns', () => {
  it('renders without crashing', () => {
    render(<DemoPatterns />);
    expect(screen.getByText('AIde Pattern Library')).toBeInTheDocument();
  });

  it('renders the demo header', () => {
    render(<DemoPatterns />);
    expect(screen.getByText('AIde Pattern Library')).toBeInTheDocument();
    expect(screen.getByText(/Comprehensive demonstration/)).toBeInTheDocument();
  });

  it('renders badges with entity count', () => {
    render(<DemoPatterns />);
    expect(screen.getByText('Read-only')).toBeInTheDocument();
    expect(screen.getByText('All Patterns')).toBeInTheDocument();
    expect(screen.getByText(/82 Entities/)).toBeInTheDocument();
  });

  it('renders the Preview component', () => {
    const { container } = render(<DemoPatterns />);
    const preview = container.querySelector('.aide-preview');
    expect(preview).toBeInTheDocument();
  });

  it('uses production SPA rendering code', () => {
    const { container } = render(<DemoPatterns />);
    const preview = container.querySelector('.aide-preview');

    // Verify Shadow DOM is used (same as production)
    expect(preview.shadowRoot).toBeTruthy();
  });

  it('uses comprehensive demo entity tree', () => {
    const tree = getDemoEntityTree();

    // Verify tree has all required pattern types
    const displays = Object.values(tree.entities).map(e => e.display).filter(Boolean);
    expect(displays).toContain('page');
    expect(displays).toContain('section');
    expect(displays).toContain('card');
    expect(displays).toContain('metric');
    expect(displays).toContain('text');
    expect(displays).toContain('image');
    expect(displays).toContain('checklist');
    expect(displays).toContain('table');
    expect(displays).toContain('list');
  });

  it('demo tree includes edge cases', () => {
    const tree = getDemoEntityTree();

    // Check for long text
    const hasLongText = Object.values(tree.entities).some(e => {
      const text = e.props?.text || '';
      return text.length > 200;
    });
    expect(hasLongText).toBe(true);

    // Check for special characters
    const hasSpecialChars = Object.values(tree.entities).some(e => {
      const text = JSON.stringify(e.props);
      return text.includes('<script>');
    });
    expect(hasSpecialChars).toBe(true);

    // Check for deep nesting
    const depths = {};
    function calculateDepth(entityId, depth = 0) {
      depths[entityId] = depth;
      Object.values(tree.entities)
        .filter(e => e.parent === entityId)
        .forEach(child => calculateDepth(child.id, depth + 1));
    }
    tree.rootIds.forEach(id => calculateDepth(id));
    const maxDepth = Math.max(...Object.values(depths));
    expect(maxDepth).toBeGreaterThanOrEqual(3);
  });

  it('provides mock data with real-world scenarios', () => {
    const tree = getDemoEntityTree();
    const allText = JSON.stringify(tree.entities).toLowerCase();

    // Check for budget scenario
    expect(allText).toContain('budget');

    // Check for task scenario
    expect(allText).toContain('task');

    // Check for multiple metrics
    const metrics = Object.values(tree.entities).filter(e => e.display === 'metric');
    expect(metrics.length).toBeGreaterThan(3);
  });
});
