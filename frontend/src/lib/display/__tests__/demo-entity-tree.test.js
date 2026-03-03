/**
 * demo-entity-tree.test.js - Tests for demo entity tree structure
 *
 * Verifies that the demo entity tree has complete coverage of all patterns
 * and edge cases.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { getDemoEntityTree } from '../demo-entity-tree.js';

describe('Demo Entity Tree', () => {
  let demoTree;

  beforeEach(() => {
    demoTree = getDemoEntityTree();
  });

  it('exports a valid entity store structure', () => {
    expect(demoTree).toHaveProperty('entities');
    expect(demoTree).toHaveProperty('rootIds');
    expect(typeof demoTree.entities).toBe('object');
    expect(Array.isArray(demoTree.rootIds)).toBe(true);
  });

  describe('Pattern Coverage', () => {
    it('includes page pattern', () => {
      const pages = Object.values(demoTree.entities).filter(e => e.display === 'page');
      expect(pages.length).toBeGreaterThan(0);
    });

    it('includes section pattern', () => {
      const sections = Object.values(demoTree.entities).filter(e => e.display === 'section');
      expect(sections.length).toBeGreaterThan(0);
    });

    it('includes card pattern', () => {
      const cards = Object.values(demoTree.entities).filter(e => e.display === 'card');
      expect(cards.length).toBeGreaterThan(0);
    });

    it('includes metric pattern', () => {
      const metrics = Object.values(demoTree.entities).filter(e => e.display === 'metric');
      expect(metrics.length).toBeGreaterThan(0);
    });

    it('includes text pattern', () => {
      const texts = Object.values(demoTree.entities).filter(e => e.display === 'text');
      expect(texts.length).toBeGreaterThan(0);
    });

    it('includes image pattern', () => {
      const images = Object.values(demoTree.entities).filter(e => e.display === 'image');
      expect(images.length).toBeGreaterThan(0);
    });

    it('includes checklist pattern', () => {
      const checklists = Object.values(demoTree.entities).filter(e => e.display === 'checklist');
      expect(checklists.length).toBeGreaterThan(0);
    });

    it('includes table pattern', () => {
      const tables = Object.values(demoTree.entities).filter(e => e.display === 'table');
      expect(tables.length).toBeGreaterThan(0);
    });

    it('includes list pattern', () => {
      const lists = Object.values(demoTree.entities).filter(e => e.display === 'list');
      expect(lists.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Case Coverage', () => {
    it('includes entities with empty props', () => {
      const emptyProps = Object.values(demoTree.entities).filter(
        e => e.props && Object.keys(e.props).filter(k => !k.startsWith('_')).length === 0
      );
      expect(emptyProps.length).toBeGreaterThan(0);
    });

    it('includes long text content', () => {
      const longTexts = Object.values(demoTree.entities).filter(e => {
        const text = e.props?.text || e.props?.content || '';
        return text.length > 200;
      });
      expect(longTexts.length).toBeGreaterThan(0);
    });

    it('includes deep nesting (3+ levels)', () => {
      const depths = {};

      function calculateDepth(entityId, depth = 0) {
        depths[entityId] = depth;
        const children = Object.values(demoTree.entities).filter(e => e.parent === entityId);
        children.forEach(child => calculateDepth(child.id, depth + 1));
      }

      demoTree.rootIds.forEach(id => calculateDepth(id));
      const maxDepth = Math.max(...Object.values(depths));
      expect(maxDepth).toBeGreaterThanOrEqual(3);
    });

    it('includes entities with many children (5+)', () => {
      const childCounts = {};
      Object.values(demoTree.entities).forEach(e => {
        if (e.parent) {
          childCounts[e.parent] = (childCounts[e.parent] || 0) + 1;
        }
      });
      const maxChildren = Math.max(...Object.values(childCounts));
      expect(maxChildren).toBeGreaterThanOrEqual(5);
    });

    it('includes entities with _created_seq for ordering', () => {
      const withSeq = Object.values(demoTree.entities).filter(e => e._created_seq !== undefined);
      expect(withSeq.length).toBeGreaterThan(0);
    });
  });

  describe('Prop Variant Coverage', () => {
    it('includes title prop variants', () => {
      const withTitle = Object.values(demoTree.entities).filter(e => e.props?.title);
      expect(withTitle.length).toBeGreaterThan(0);
    });

    it('includes name prop variants', () => {
      const withName = Object.values(demoTree.entities).filter(e => e.props?.name);
      expect(withName.length).toBeGreaterThan(0);
    });

    it('includes value/count prop variants for metrics', () => {
      const metrics = Object.values(demoTree.entities).filter(e => e.display === 'metric');
      const withValue = metrics.filter(e => e.props?.value !== undefined);
      const withCount = metrics.filter(e => e.props?.count !== undefined);
      expect(withValue.length).toBeGreaterThan(0);
      expect(withCount.length).toBeGreaterThan(0);
    });

    it('includes done/checked prop variants for checklist items', () => {
      const checklistItems = Object.values(demoTree.entities).filter(e => {
        const parent = demoTree.entities[e.parent];
        return parent?.display === 'checklist';
      });
      const withDone = checklistItems.filter(e => typeof e.props?.done === 'boolean');
      const withChecked = checklistItems.filter(e => typeof e.props?.checked === 'boolean');
      expect(withDone.length).toBeGreaterThan(0);
      expect(withChecked.length).toBeGreaterThan(0);
    });

    it('includes task/label prop variants for checklist items', () => {
      const checklistItems = Object.values(demoTree.entities).filter(e => {
        const parent = demoTree.entities[e.parent];
        return parent?.display === 'checklist';
      });
      const withTask = checklistItems.filter(e => e.props?.task);
      const withLabel = checklistItems.filter(e => e.props?.label);
      expect(withTask.length).toBeGreaterThan(0);
      expect(withLabel.length).toBeGreaterThan(0);
    });

    it('includes text/content/body prop variants for text entities', () => {
      const texts = Object.values(demoTree.entities).filter(e => e.display === 'text');
      const withText = texts.filter(e => e.props?.text);
      const withContent = texts.filter(e => e.props?.content);
      const withBody = texts.filter(e => e.props?.body);
      expect(withText.length).toBeGreaterThan(0);
      // At least one variant should be present
      expect(withText.length + withContent.length + withBody.length).toBe(texts.length);
    });

    it('includes src/url prop variants for images', () => {
      const images = Object.values(demoTree.entities).filter(e => e.display === 'image');
      const withSrc = images.filter(e => e.props?.src);
      const withUrl = images.filter(e => e.props?.url);
      expect(withSrc.length).toBeGreaterThan(0);
      // Either src or url should be present
      expect(withSrc.length + withUrl.length).toBe(images.length);
    });
  });

  describe('Real-World Scenarios', () => {
    it('includes budget tracker scenario', () => {
      const budgetRelated = Object.values(demoTree.entities).filter(e => {
        const text = JSON.stringify(e.props).toLowerCase();
        return text.includes('budget') || text.includes('expense') || text.includes('income');
      });
      expect(budgetRelated.length).toBeGreaterThan(0);
    });

    it('includes task/checklist scenario', () => {
      const taskRelated = Object.values(demoTree.entities).filter(e => {
        const text = JSON.stringify(e.props).toLowerCase();
        return text.includes('task') || text.includes('todo') || text.includes('checklist');
      });
      expect(taskRelated.length).toBeGreaterThan(0);
    });

    it('includes dashboard/metrics scenario', () => {
      const dashboardRelated = Object.values(demoTree.entities).filter(e => {
        return e.display === 'metric' ||
               (e.props && (e.props.label || e.props.value || e.props.count));
      });
      expect(dashboardRelated.length).toBeGreaterThan(3); // Multiple metrics
    });
  });

  describe('Data Integrity', () => {
    it('has valid parent references', () => {
      Object.values(demoTree.entities).forEach(entity => {
        if (entity.parent) {
          expect(demoTree.entities[entity.parent]).toBeDefined();
        }
      });
    });

    it('has all rootIds present in entities', () => {
      demoTree.rootIds.forEach(rootId => {
        expect(demoTree.entities[rootId]).toBeDefined();
      });
    });

    it('root entities have no parent', () => {
      demoTree.rootIds.forEach(rootId => {
        const entity = demoTree.entities[rootId];
        expect(entity.parent).toBeUndefined();
      });
    });

    it('all entities have unique ids', () => {
      const ids = Object.keys(demoTree.entities);
      const uniqueIds = new Set(ids);
      expect(uniqueIds.size).toBe(ids.length);
    });

    it('all entities have an id property matching their key', () => {
      Object.entries(demoTree.entities).forEach(([key, entity]) => {
        expect(entity.id).toBe(key);
      });
    });
  });
});
