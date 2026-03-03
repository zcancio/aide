/**
 * demo-patterns.test.js - Tests for all pattern types and display hints
 *
 * This file ensures that all supported pattern types render correctly
 * and that the demo entity tree covers comprehensive test cases.
 */

import { describe, it, expect } from 'vitest';
import { renderHtml } from '../render-html.js';

describe('Pattern Rendering', () => {
  describe('page pattern', () => {
    it('renders page with title', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', display: 'page', props: { title: 'My Page' } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-page');
      expect(html).toContain('My Page');
    });

    it('renders page with name fallback', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', display: 'page', props: { name: 'Page Name' } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Page Name');
    });

    it('renders page with children', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', display: 'page', props: { title: 'Page' } },
          'c1': { id: 'c1', parent: 'p1', display: 'text', props: { text: 'Child text' } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Child text');
    });

    it('renders empty state when no children', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', display: 'page', props: {} }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-empty');
    });
  });

  describe('section pattern', () => {
    it('renders section with title', () => {
      const store = {
        entities: {
          's1': { id: 's1', display: 'section', props: { title: 'Section Title' } }
        },
        rootIds: ['s1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-section');
      expect(html).toContain('Section Title');
    });

    it('renders section with children', () => {
      const store = {
        entities: {
          's1': { id: 's1', display: 'section', props: { title: 'Section' } },
          'c1': { id: 'c1', parent: 's1', display: 'text', props: { text: 'Content' } }
        },
        rootIds: ['s1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Content');
    });
  });

  describe('metric pattern', () => {
    it('renders metric with label and value', () => {
      const store = {
        entities: {
          'm1': { id: 'm1', display: 'metric', props: { label: 'Budget', value: '$1,350' } }
        },
        rootIds: ['m1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-metric');
      expect(html).toContain('Budget');
      expect(html).toContain('$1,350');
    });

    it('renders metric with count fallback', () => {
      const store = {
        entities: {
          'm1': { id: 'm1', display: 'metric', props: { label: 'Tasks', count: 42 } }
        },
        rootIds: ['m1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Tasks');
      expect(html).toContain('42');
    });

    it('renders metric with name fallback', () => {
      const store = {
        entities: {
          'm1': { id: 'm1', display: 'metric', props: { name: 'Items', value: 100 } }
        },
        rootIds: ['m1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Items');
      expect(html).toContain('100');
    });
  });

  describe('text pattern', () => {
    it('renders text with text prop', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'text', props: { text: 'Sample text content' } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-text');
      expect(html).toContain('Sample text content');
    });

    it('renders text with content fallback', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'text', props: { content: 'Content fallback' } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Content fallback');
    });

    it('renders text with body fallback', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'text', props: { body: 'Body fallback' } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Body fallback');
    });
  });

  describe('image pattern', () => {
    it('renders image with src', () => {
      const store = {
        entities: {
          'i1': { id: 'i1', display: 'image', props: { src: 'https://example.com/img.jpg', alt: 'Test image' } }
        },
        rootIds: ['i1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-image');
      expect(html).toContain('https://example.com/img.jpg');
      expect(html).toContain('Test image');
    });

    it('renders image with url fallback', () => {
      const store = {
        entities: {
          'i1': { id: 'i1', display: 'image', props: { url: 'https://example.com/pic.png' } }
        },
        rootIds: ['i1']
      };
      const html = renderHtml(store);
      expect(html).toContain('https://example.com/pic.png');
    });

    it('renders image with caption', () => {
      const store = {
        entities: {
          'i1': { id: 'i1', display: 'image', props: { src: 'img.jpg', caption: 'Figure 1' } }
        },
        rootIds: ['i1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Figure 1');
      expect(html).toContain('aide-image__caption');
    });
  });

  describe('checklist pattern', () => {
    it('renders checklist with items', () => {
      const store = {
        entities: {
          'cl1': { id: 'cl1', display: 'checklist', props: { title: 'Tasks' } },
          'i1': { id: 'i1', parent: 'cl1', props: { task: 'First task', done: false } },
          'i2': { id: 'i2', parent: 'cl1', props: { task: 'Second task', done: true } }
        },
        rootIds: ['cl1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-checklist');
      expect(html).toContain('First task');
      expect(html).toContain('Second task');
      expect(html).toContain('checked');
    });

    it('renders checklist with checked fallback', () => {
      const store = {
        entities: {
          'cl1': { id: 'cl1', display: 'checklist', props: { title: 'Items' } },
          'i1': { id: 'i1', parent: 'cl1', props: { label: 'Item', checked: true } }
        },
        rootIds: ['cl1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Item');
      expect(html).toContain('checked');
    });

    it('renders checklist summary', () => {
      const store = {
        entities: {
          'cl1': { id: 'cl1', display: 'checklist', props: { name: 'Checklist' } },
          'i1': { id: 'i1', parent: 'cl1', props: { task: 'Done', done: true } },
          'i2': { id: 'i2', parent: 'cl1', props: { task: 'Pending', done: false } }
        },
        rootIds: ['cl1']
      };
      const html = renderHtml(store);
      expect(html).toContain('1 of 2 complete');
    });
  });

  describe('table pattern', () => {
    it('renders table with rows', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'table', props: {} },
          'r1': { id: 'r1', parent: 't1', props: { name: 'Alice', age: 30 } },
          'r2': { id: 'r2', parent: 't1', props: { name: 'Bob', age: 25 } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-table');
      expect(html).toContain('Alice');
      expect(html).toContain('Bob');
      expect(html).toContain('30');
      expect(html).toContain('25');
    });

    it('renders table headers from properties', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'table', props: {} },
          'r1': { id: 'r1', parent: 't1', props: { item_name: 'Widget', quantity: 10 } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Item Name'); // humanized
      expect(html).toContain('Quantity');
    });

    it('renders empty state when no rows', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'table', props: {} }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-collection-empty');
    });
  });

  describe('list pattern', () => {
    it('renders list with items', () => {
      const store = {
        entities: {
          'l1': { id: 'l1', display: 'list', props: {} },
          'i1': { id: 'i1', parent: 'l1', props: { name: 'Item 1', status: 'active' } },
          'i2': { id: 'i2', parent: 'l1', props: { name: 'Item 2', status: 'pending' } }
        },
        rootIds: ['l1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-list');
      expect(html).toContain('Item 1');
      expect(html).toContain('Item 2');
    });

    it('renders list with title fallback', () => {
      const store = {
        entities: {
          'l1': { id: 'l1', display: 'list', props: {} },
          'i1': { id: 'i1', parent: 'l1', props: { title: 'Title Item' } }
        },
        rootIds: ['l1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Title Item');
    });
  });

  describe('card pattern (default)', () => {
    it('renders card with title and fields', () => {
      const store = {
        entities: {
          'c1': { id: 'c1', display: 'card', props: { title: 'Card Title', status: 'active', priority: 'high' } }
        },
        rootIds: ['c1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-card');
      expect(html).toContain('Card Title');
      expect(html).toContain('Status');
      expect(html).toContain('active');
      expect(html).toContain('Priority');
      expect(html).toContain('high');
    });

    it('renders card with name fallback', () => {
      const store = {
        entities: {
          'c1': { id: 'c1', display: 'card', props: { name: 'Card Name', value: 100 } }
        },
        rootIds: ['c1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Card Name');
      expect(html).toContain('100');
    });

    it('renders card with children', () => {
      const store = {
        entities: {
          'c1': { id: 'c1', display: 'card', props: { title: 'Parent' } },
          'ch1': { id: 'ch1', parent: 'c1', display: 'text', props: { text: 'Child content' } }
        },
        rootIds: ['c1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Child content');
    });
  });

  describe('Edge Cases', () => {
    it('handles empty props gracefully', () => {
      const store = {
        entities: {
          'e1': { id: 'e1', display: 'card', props: {} }
        },
        rootIds: ['e1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-card');
    });

    it('handles long text content', () => {
      const longText = 'Lorem ipsum dolor sit amet, '.repeat(50);
      const store = {
        entities: {
          't1': { id: 't1', display: 'text', props: { text: longText } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain(longText);
    });

    it('handles deep nesting (3+ levels)', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', display: 'page', props: { title: 'Page' } },
          's1': { id: 's1', parent: 'p1', display: 'section', props: { title: 'Section' } },
          'c1': { id: 'c1', parent: 's1', display: 'card', props: { title: 'Card' } },
          't1': { id: 't1', parent: 'c1', display: 'text', props: { text: 'Deep text' } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('Deep text');
    });

    it('handles special characters in content', () => {
      const store = {
        entities: {
          't1': { id: 't1', display: 'text', props: { text: '<script>alert("xss")</script>' } }
        },
        rootIds: ['t1']
      };
      const html = renderHtml(store);
      expect(html).toContain('&lt;script&gt;');
      expect(html).not.toContain('<script>');
    });

    it('handles removed entities', () => {
      const store = {
        entities: {
          'e1': { id: 'e1', display: 'text', props: { text: 'Visible' } },
          'e2': { id: 'e2', display: 'text', props: { text: 'Removed' }, _removed: true }
        },
        rootIds: ['e1', 'e2']
      };
      const html = renderHtml(store);
      expect(html).toContain('Visible');
      expect(html).not.toContain('Removed');
    });

    it('handles many children (10+)', () => {
      const entities = {
        'l1': { id: 'l1', display: 'list', props: {} }
      };
      for (let i = 1; i <= 15; i++) {
        entities[`i${i}`] = { id: `i${i}`, parent: 'l1', props: { name: `Item ${i}` } };
      }
      const store = { entities, rootIds: ['l1'] };
      const html = renderHtml(store);
      expect(html).toContain('Item 1');
      expect(html).toContain('Item 15');
    });

    it('sorts children by _created_seq', () => {
      const store = {
        entities: {
          'l1': { id: 'l1', display: 'list', props: {} },
          'i1': { id: 'i1', parent: 'l1', props: { name: 'First' }, _created_seq: 1 },
          'i2': { id: 'i2', parent: 'l1', props: { name: 'Second' }, _created_seq: 2 },
          'i3': { id: 'i3', parent: 'l1', props: { name: 'Third' }, _created_seq: 3 }
        },
        rootIds: ['l1']
      };
      const html = renderHtml(store);
      const firstIndex = html.indexOf('First');
      const secondIndex = html.indexOf('Second');
      const thirdIndex = html.indexOf('Third');
      expect(firstIndex).toBeLessThan(secondIndex);
      expect(secondIndex).toBeLessThan(thirdIndex);
    });
  });

  describe('Display Hint Resolution', () => {
    it('auto-detects image from src prop', () => {
      const store = {
        entities: {
          'e1': { id: 'e1', props: { src: 'image.jpg' } }
        },
        rootIds: ['e1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-image');
    });

    it('auto-detects metric from value prop', () => {
      const store = {
        entities: {
          'e1': { id: 'e1', props: { label: 'Count', value: 42 } }
        },
        rootIds: ['e1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-metric');
    });

    it('auto-detects checklist from children with done prop', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', props: {} },
          'c1': { id: 'c1', parent: 'p1', props: { task: 'Task', done: false } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-checklist');
    });

    it('auto-detects table from children without done prop', () => {
      const store = {
        entities: {
          'p1': { id: 'p1', props: {} },
          'r1': { id: 'r1', parent: 'p1', props: { name: 'Row', value: 100 } }
        },
        rootIds: ['p1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-table');
    });

    it('respects explicit display hint over auto-detection', () => {
      const store = {
        entities: {
          'e1': { id: 'e1', display: 'text', props: { src: 'image.jpg' } }
        },
        rootIds: ['e1']
      };
      const html = renderHtml(store);
      expect(html).toContain('aide-text');
      expect(html).not.toContain('aide-image');
    });
  });
});
