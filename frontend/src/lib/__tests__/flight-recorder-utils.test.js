import { describe, it, expect } from 'vitest';
import {
  calculateCost,
  parseToolCalls,
  mkTree,
  eDiff,
  buildSnapshot,
  COST_RATES,
} from '../flight-recorder-utils.js';

describe('flight-recorder-utils', () => {
  describe('COST_RATES', () => {
    it('has rates for L2, L3, and L4 tiers', () => {
      expect(COST_RATES.L2).toBeDefined();
      expect(COST_RATES.L3).toBeDefined();
      expect(COST_RATES.L4).toBeDefined();
    });

    it('L4 has highest rates', () => {
      expect(COST_RATES.L4.in).toBeGreaterThan(COST_RATES.L3.in);
      expect(COST_RATES.L3.in).toBeGreaterThan(COST_RATES.L2.in);
    });
  });

  describe('calculateCost', () => {
    it('returns 0 for null/undefined usage', () => {
      expect(calculateCost(null, 'L3')).toBe(0);
      expect(calculateCost(undefined, 'L3')).toBe(0);
    });

    it('calculates cost for L3 tier with input/output tokens', () => {
      const usage = { input_tokens: 1000, output_tokens: 100 };
      const cost = calculateCost(usage, 'L3');
      // L3: input=$3/1M, output=$15/1M
      // 1000 * 3 / 1e6 + 100 * 15 / 1e6 = 0.003 + 0.0015 = 0.0045
      expect(cost).toBeCloseTo(0.0045, 6);
    });

    it('calculates cost for L4 tier', () => {
      const usage = { input_tokens: 1000, output_tokens: 100 };
      const cost = calculateCost(usage, 'L4');
      // L4: input=$15/1M, output=$75/1M
      // 1000 * 15 / 1e6 + 100 * 75 / 1e6 = 0.015 + 0.0075 = 0.0225
      expect(cost).toBeCloseTo(0.0225, 6);
    });

    it('calculates cost for L2 tier', () => {
      const usage = { input_tokens: 1000, output_tokens: 100 };
      const cost = calculateCost(usage, 'L2');
      // L2: input=$0.25/1M, output=$1.25/1M
      // 1000 * 0.25 / 1e6 + 100 * 1.25 / 1e6 = 0.00025 + 0.000125 = 0.000375
      expect(cost).toBeCloseTo(0.000375, 6);
    });

    it('includes cache_read in cost calculation', () => {
      const usage = { input_tokens: 1000, output_tokens: 100, cache_read: 500 };
      const cost = calculateCost(usage, 'L3');
      // L3: input=$3/1M, output=$15/1M, cache_read=$0.3/1M
      // 1000 * 3 / 1e6 + 100 * 15 / 1e6 + 500 * 0.3 / 1e6
      expect(cost).toBeCloseTo(0.003 + 0.0015 + 0.00015, 6);
    });

    it('includes cache_creation in cost calculation', () => {
      const usage = { input_tokens: 1000, output_tokens: 100, cache_creation: 200 };
      const cost = calculateCost(usage, 'L3');
      // L3: cache_write=$3.75/1M
      // 1000 * 3 / 1e6 + 100 * 15 / 1e6 + 200 * 3.75 / 1e6
      expect(cost).toBeCloseTo(0.003 + 0.0015 + 0.00075, 6);
    });

    it('defaults to L3 rates for unknown tier', () => {
      const usage = { input_tokens: 1000, output_tokens: 100 };
      const costUnknown = calculateCost(usage, 'UNKNOWN');
      const costL3 = calculateCost(usage, 'L3');
      expect(costUnknown).toBe(costL3);
    });

    it('handles tier with arrow notation (e.g., "L3->L4")', () => {
      const usage = { input_tokens: 1000, output_tokens: 100 };
      const cost = calculateCost(usage, 'L3->L4');
      const costL3 = calculateCost(usage, 'L3');
      expect(cost).toBe(costL3); // Should use first part before arrow
    });
  });

  describe('parseToolCalls', () => {
    it('returns empty array for null/undefined input', () => {
      expect(parseToolCalls(null)).toEqual([]);
      expect(parseToolCalls(undefined)).toEqual([]);
    });

    it('returns empty array for non-array input', () => {
      expect(parseToolCalls('not an array')).toEqual([]);
      expect(parseToolCalls({})).toEqual([]);
    });

    it('parses tool calls with type and input fields', () => {
      const toolCalls = [
        { type: 'entity.create', input: { id: 'e1', parent: 'root' } },
        { type: 'entity.update', input: { ref: 'e1', p: { name: 'test' } } },
      ];
      const result = parseToolCalls(toolCalls);
      expect(result).toEqual([
        { t: 'entity.create', id: 'e1', parent: 'root' },
        { t: 'entity.update', ref: 'e1', p: { name: 'test' } },
      ]);
    });

    it('passes through tool calls that already have t field', () => {
      const toolCalls = [
        { t: 'entity.create', id: 'e1' },
        { t: 'meta.set', p: { title: 'Test' } },
      ];
      const result = parseToolCalls(toolCalls);
      expect(result).toEqual(toolCalls);
    });

    it('filters out falsy values', () => {
      const toolCalls = [
        { type: 'entity.create', input: { id: 'e1' } },
        null,
        undefined,
        { t: 'meta.set', p: {} },
      ];
      const result = parseToolCalls(toolCalls);
      expect(result).toHaveLength(2);
    });
  });

  describe('mkTree', () => {
    it('returns empty array for null/undefined entities', () => {
      expect(mkTree(null)).toEqual([]);
      expect(mkTree(undefined)).toEqual([]);
    });

    it('builds tree with correct depth for nested entities', () => {
      const entities = {
        page: { id: 'page', parent: 'root', display: 'page', props: {} },
        section: { id: 'section', parent: 'page', display: 'section', props: {} },
        card: { id: 'card', parent: 'section', display: 'card', props: {} },
      };
      const tree = mkTree(entities);

      expect(tree).toHaveLength(3);
      expect(tree.find(e => e.id === 'page').depth).toBe(0);
      expect(tree.find(e => e.id === 'section').depth).toBe(1);
      expect(tree.find(e => e.id === 'card').depth).toBe(2);
    });

    it('includes removed entities with _removed flag', () => {
      const entities = {
        page: { id: 'page', parent: 'root', props: {} },
      };
      const removedEnts = {
        deleted: { id: 'deleted', parent: 'page', props: {} },
      };
      const tree = mkTree(entities, removedEnts);

      const deletedNode = tree.find(e => e.id === 'deleted');
      expect(deletedNode).toBeDefined();
      expect(deletedNode._removed).toBe(true);
    });

    it('marks orphaned entities with _orphan flag', () => {
      const entities = {
        orphan: { id: 'orphan', parent: 'nonexistent', props: {} },
      };
      const tree = mkTree(entities);

      expect(tree).toHaveLength(1);
      expect(tree[0]._orphan).toBe(true);
    });

    it('handles entities with missing parent (defaults to root)', () => {
      const entities = {
        noParent: { id: 'noParent', props: { name: 'test' } },
      };
      const tree = mkTree(entities);

      expect(tree).toHaveLength(1);
      expect(tree[0].depth).toBe(0);
    });

    it('sorts removed entities after non-removed at same level', () => {
      const entities = {
        a: { id: 'a', parent: 'root', props: {} },
      };
      const removedEnts = {
        b: { id: 'b', parent: 'root', props: {} },
      };
      const tree = mkTree(entities, removedEnts);

      const aIndex = tree.findIndex(e => e.id === 'a');
      const bIndex = tree.findIndex(e => e.id === 'b');
      expect(aIndex).toBeLessThan(bIndex);
    });
  });

  describe('eDiff', () => {
    it('returns empty diff for identical snapshots', () => {
      const snapshot = { e1: { id: 'e1', props: { name: 'A' } } };
      const diff = eDiff(snapshot, snapshot);

      expect(diff.add).toEqual([]);
      expect(diff.rem).toEqual([]);
      expect(diff.mod).toEqual([]);
    });

    it('detects added entities', () => {
      const before = { e1: { id: 'e1', props: {} } };
      const after = {
        e1: { id: 'e1', props: {} },
        e2: { id: 'e2', props: {} },
      };
      const diff = eDiff(before, after);

      expect(diff.add).toContain('e2');
      expect(diff.rem).toEqual([]);
    });

    it('detects removed entities', () => {
      const before = {
        e1: { id: 'e1', props: {} },
        e2: { id: 'e2', props: {} },
      };
      const after = { e1: { id: 'e1', props: {} } };
      const diff = eDiff(before, after);

      expect(diff.rem).toContain('e2');
      expect(diff.add).toEqual([]);
    });

    it('detects modified entities', () => {
      const before = { e1: { id: 'e1', props: { name: 'A' } } };
      const after = { e1: { id: 'e1', props: { name: 'B' } } };
      const diff = eDiff(before, after);

      expect(diff.mod).toContain('e1');
      expect(diff.modDetails.e1).toContain('name: "A"->"B"');
    });

    it('detects moved entities (parent change)', () => {
      const before = { e1: { id: 'e1', parent: 'p1', props: {} } };
      const after = { e1: { id: 'e1', parent: 'p2', props: {} } };
      const diff = eDiff(before, after);

      expect(diff.moved.e1).toEqual({ from: 'p1', to: 'p2' });
      expect(diff.mod).toContain('e1');
    });

    it('detects added props', () => {
      const before = { e1: { id: 'e1', props: {} } };
      const after = { e1: { id: 'e1', props: { newProp: 'value' } } };
      const diff = eDiff(before, after);

      expect(diff.mod).toContain('e1');
      expect(diff.modDetails.e1).toContain('+newProp');
    });

    it('detects removed props', () => {
      const before = { e1: { id: 'e1', props: { oldProp: 'value' } } };
      const after = { e1: { id: 'e1', props: {} } };
      const diff = eDiff(before, after);

      expect(diff.mod).toContain('e1');
      expect(diff.modDetails.e1).toContain('-oldProp');
    });

    it('handles null/undefined inputs', () => {
      expect(eDiff(null, null)).toEqual({
        add: [],
        rem: [],
        mod: [],
        modDetails: {},
        moved: {},
      });
      expect(eDiff(undefined, { e1: { id: 'e1', props: {} } })).toEqual({
        add: ['e1'],
        rem: [],
        mod: [],
        modDetails: {},
        moved: {},
      });
    });

    it('handles p field as alias for props', () => {
      const before = { e1: { id: 'e1', p: { name: 'A' } } };
      const after = { e1: { id: 'e1', p: { name: 'B' } } };
      const diff = eDiff(before, after);

      expect(diff.mod).toContain('e1');
    });
  });

  describe('buildSnapshot', () => {
    it('returns empty snapshot for empty turns', () => {
      const snapshot = buildSnapshot([], 0);
      expect(snapshot).toEqual({ meta: {}, entities: {} });
    });

    it('applies meta.set events', () => {
      const turns = [
        {
          tool_calls: [{ t: 'meta.set', p: { title: 'Test Page' } }],
        },
      ];
      const snapshot = buildSnapshot(turns, 0);
      expect(snapshot.meta.title).toBe('Test Page');
    });

    it('applies meta.update events', () => {
      const turns = [
        { tool_calls: [{ t: 'meta.set', p: { title: 'A' } }] },
        { tool_calls: [{ t: 'meta.update', p: { subtitle: 'B' } }] },
      ];
      const snapshot = buildSnapshot(turns, 1);
      expect(snapshot.meta).toEqual({ title: 'A', subtitle: 'B' });
    });

    it('applies entity.create events', () => {
      const turns = [
        {
          tool_calls: [
            { t: 'entity.create', id: 'e1', parent: 'root', display: 'card', p: { name: 'Test' } },
          ],
        },
      ];
      const snapshot = buildSnapshot(turns, 0);
      expect(snapshot.entities.e1).toEqual({
        id: 'e1',
        parent: 'root',
        display: 'card',
        props: { name: 'Test' },
      });
    });

    it('applies entity.update events', () => {
      const turns = [
        { tool_calls: [{ t: 'entity.create', id: 'e1', p: { name: 'A' } }] },
        { tool_calls: [{ t: 'entity.update', ref: 'e1', p: { name: 'B' } }] },
      ];
      const snapshot = buildSnapshot(turns, 1);
      expect(snapshot.entities.e1.props.name).toBe('B');
    });

    it('applies entity.remove events', () => {
      const turns = [
        { tool_calls: [{ t: 'entity.create', id: 'e1', p: {} }] },
        { tool_calls: [{ t: 'entity.remove', ref: 'e1' }] },
      ];
      const snapshot = buildSnapshot(turns, 1);
      expect(snapshot.entities.e1).toBeUndefined();
    });

    it('builds snapshot up to specified index only', () => {
      const turns = [
        { tool_calls: [{ t: 'entity.create', id: 'e1', p: {} }] },
        { tool_calls: [{ t: 'entity.create', id: 'e2', p: {} }] },
        { tool_calls: [{ t: 'entity.create', id: 'e3', p: {} }] },
      ];
      const snapshot = buildSnapshot(turns, 1);
      expect(Object.keys(snapshot.entities)).toEqual(['e1', 'e2']);
      expect(snapshot.entities.e3).toBeUndefined();
    });

    it('handles tool_calls in type/input format', () => {
      const turns = [
        {
          tool_calls: [
            { type: 'entity.create', input: { id: 'e1', parent: 'root', p: { name: 'Test' } } },
          ],
        },
      ];
      const snapshot = buildSnapshot(turns, 0);
      expect(snapshot.entities.e1).toBeDefined();
    });

    it('ignores entity.update for non-existent entities', () => {
      const turns = [
        { tool_calls: [{ t: 'entity.update', ref: 'nonexistent', p: { name: 'X' } }] },
      ];
      const snapshot = buildSnapshot(turns, 0);
      expect(snapshot.entities.nonexistent).toBeUndefined();
    });
  });
});
