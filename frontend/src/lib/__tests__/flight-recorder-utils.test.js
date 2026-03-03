import { describe, it, expect } from 'vitest';
import {
  parseEvents,
  buildTree,
  computeDiff,
  calculateCost,
  normalizeTurn,
} from '../flight-recorder-utils';

describe('parseEvents', () => {
  it('returns empty array for null/undefined input', () => {
    expect(parseEvents(null)).toEqual([]);
    expect(parseEvents(undefined)).toEqual([]);
    expect(parseEvents('')).toEqual([]);
  });

  it('parses single JSONL line', () => {
    const output = '{"t":"entity.create","id":"foo"}';
    const result = parseEvents(output);
    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({ t: 'entity.create', id: 'foo' });
  });

  it('parses multiple JSONL lines', () => {
    const output = `{"t":"meta.set","p":{"title":"Test"}}
{"t":"entity.create","id":"page","parent":"root"}
{"t":"voice","text":"Done."}`;
    const result = parseEvents(output);
    expect(result).toHaveLength(3);
    expect(result[0].t).toBe('meta.set');
    expect(result[1].t).toBe('entity.create');
    expect(result[2].t).toBe('voice');
  });

  it('skips lines starting with backticks (code fences)', () => {
    const output = `\`\`\`json
{"t":"entity.create","id":"foo"}
\`\`\``;
    const result = parseEvents(output);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('foo');
  });

  it('skips invalid JSON lines gracefully', () => {
    const output = `{"t":"valid"}
not valid json
{"t":"also_valid"}`;
    const result = parseEvents(output);
    expect(result).toHaveLength(2);
    expect(result[0].t).toBe('valid');
    expect(result[1].t).toBe('also_valid');
  });

  it('handles empty lines', () => {
    const output = `{"t":"one"}

{"t":"two"}

{"t":"three"}`;
    const result = parseEvents(output);
    expect(result).toHaveLength(3);
  });
});

describe('buildTree', () => {
  it('returns empty array for null/undefined entities', () => {
    expect(buildTree(null)).toEqual([]);
    expect(buildTree(undefined)).toEqual([]);
    expect(buildTree({})).toEqual([]);
  });

  it('builds flat tree for root-level entities', () => {
    const entities = {
      page: { id: 'page', parent: 'root', display: 'page' },
    };
    const result = buildTree(entities);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('page');
    expect(result[0].depth).toBe(0);
  });

  it('builds nested tree with correct depths', () => {
    const entities = {
      page: { id: 'page', parent: 'root', display: 'page' },
      section: { id: 'section', parent: 'page', display: 'section' },
      card: { id: 'card', parent: 'section', display: 'card' },
    };
    const result = buildTree(entities);
    expect(result).toHaveLength(3);

    const page = result.find(e => e.id === 'page');
    const section = result.find(e => e.id === 'section');
    const card = result.find(e => e.id === 'card');

    expect(page.depth).toBe(0);
    expect(section.depth).toBe(1);
    expect(card.depth).toBe(2);
  });

  it('marks removed entities', () => {
    const entities = {
      page: { id: 'page', parent: 'root' },
    };
    const removed = {
      deleted: { id: 'deleted', parent: 'root' },
    };
    const result = buildTree(entities, removed);
    expect(result).toHaveLength(2);

    const deletedEntity = result.find(e => e.id === 'deleted');
    expect(deletedEntity._removed).toBe(true);
  });

  it('sorts removed entities after non-removed', () => {
    const entities = {
      active: { id: 'active', parent: 'root' },
    };
    const removed = {
      deleted: { id: 'deleted', parent: 'root' },
    };
    const result = buildTree(entities, removed);

    // Active should come before deleted
    const activeIdx = result.findIndex(e => e.id === 'active');
    const deletedIdx = result.findIndex(e => e.id === 'deleted');
    expect(activeIdx).toBeLessThan(deletedIdx);
  });

  it('marks orphaned entities', () => {
    const entities = {
      orphan: { id: 'orphan', parent: 'nonexistent' },
    };
    const result = buildTree(entities);
    expect(result).toHaveLength(1);
    expect(result[0]._orphan).toBe(true);
    expect(result[0].depth).toBe(0);
  });

  it('handles entities without explicit parent (defaults to root)', () => {
    const entities = {
      implicit: { id: 'implicit' }, // no parent specified
    };
    const result = buildTree(entities);
    expect(result).toHaveLength(1);
    expect(result[0].depth).toBe(0);
  });
});

describe('computeDiff', () => {
  it('returns empty diff for identical snapshots', () => {
    const entities = { foo: { id: 'foo', props: { a: 1 } } };
    const result = computeDiff(entities, entities);
    expect(result.add).toEqual([]);
    expect(result.rem).toEqual([]);
    expect(result.mod).toEqual([]);
  });

  it('returns empty diff for null/undefined snapshots', () => {
    const result = computeDiff(null, null);
    expect(result.add).toEqual([]);
    expect(result.rem).toEqual([]);
    expect(result.mod).toEqual([]);
  });

  it('detects added entities', () => {
    const before = {};
    const after = {
      new1: { id: 'new1', props: {} },
      new2: { id: 'new2', props: {} },
    };
    const result = computeDiff(before, after);
    expect(result.add).toContain('new1');
    expect(result.add).toContain('new2');
    expect(result.add).toHaveLength(2);
  });

  it('detects removed entities', () => {
    const before = {
      old1: { id: 'old1', props: {} },
      old2: { id: 'old2', props: {} },
    };
    const after = {};
    const result = computeDiff(before, after);
    expect(result.rem).toContain('old1');
    expect(result.rem).toContain('old2');
    expect(result.rem).toHaveLength(2);
  });

  it('detects modified entities with changed props', () => {
    const before = {
      item: { id: 'item', props: { name: 'old', count: 1 } },
    };
    const after = {
      item: { id: 'item', props: { name: 'new', count: 1 } },
    };
    const result = computeDiff(before, after);
    expect(result.mod).toContain('item');
    expect(result.modDetails.item).toContain('name');
  });

  it('detects added props', () => {
    const before = {
      item: { id: 'item', props: { a: 1 } },
    };
    const after = {
      item: { id: 'item', props: { a: 1, b: 2 } },
    };
    const result = computeDiff(before, after);
    expect(result.mod).toContain('item');
    expect(result.modDetails.item).toContain('+b');
  });

  it('detects removed props', () => {
    const before = {
      item: { id: 'item', props: { a: 1, b: 2 } },
    };
    const after = {
      item: { id: 'item', props: { a: 1 } },
    };
    const result = computeDiff(before, after);
    expect(result.mod).toContain('item');
    expect(result.modDetails.item).toContain('-b');
  });

  it('detects moved entities (parent change)', () => {
    const before = {
      item: { id: 'item', parent: 'section1', props: {} },
    };
    const after = {
      item: { id: 'item', parent: 'section2', props: {} },
    };
    const result = computeDiff(before, after);
    expect(result.mod).toContain('item');
    expect(result.moved.item).toEqual({ from: 'section1', to: 'section2' });
  });

  it('handles p shorthand for props', () => {
    const before = {
      item: { id: 'item', p: { val: 'old' } },
    };
    const after = {
      item: { id: 'item', p: { val: 'new' } },
    };
    const result = computeDiff(before, after);
    expect(result.mod).toContain('item');
  });
});

describe('calculateCost', () => {
  it('returns 0 for null/undefined usage', () => {
    expect(calculateCost(null, 'L3')).toBe(0);
    expect(calculateCost(undefined, 'L3')).toBe(0);
  });

  it('calculates L3 cost correctly', () => {
    const usage = {
      input_tokens: 1000,
      output_tokens: 100,
    };
    // L3: $3/M in, $15/M out
    // Expected: (1000 * 3 + 100 * 15) / 1e6 = (3000 + 1500) / 1e6 = 0.0045
    const result = calculateCost(usage, 'L3');
    expect(result).toBeCloseTo(0.0045, 6);
  });

  it('calculates L2 cost correctly', () => {
    const usage = {
      input_tokens: 10000,
      output_tokens: 500,
    };
    // L2: $0.25/M in, $1.25/M out
    // Expected: (10000 * 0.25 + 500 * 1.25) / 1e6 = (2500 + 625) / 1e6 = 0.003125
    const result = calculateCost(usage, 'L2');
    expect(result).toBeCloseTo(0.003125, 6);
  });

  it('calculates L4 cost correctly', () => {
    const usage = {
      input_tokens: 1000,
      output_tokens: 200,
    };
    // L4: $15/M in, $75/M out
    // Expected: (1000 * 15 + 200 * 75) / 1e6 = (15000 + 15000) / 1e6 = 0.03
    const result = calculateCost(usage, 'L4');
    expect(result).toBeCloseTo(0.03, 6);
  });

  it('includes cache read costs', () => {
    const usage = {
      input_tokens: 0,
      output_tokens: 0,
      cache_read: 10000,
    };
    // L3 cache_read: $0.3/M
    // Expected: 10000 * 0.3 / 1e6 = 0.003
    const result = calculateCost(usage, 'L3');
    expect(result).toBeCloseTo(0.003, 6);
  });

  it('includes cache write costs', () => {
    const usage = {
      input_tokens: 0,
      output_tokens: 0,
      cache_creation: 10000,
    };
    // L3 cache_write: $3.75/M
    // Expected: 10000 * 3.75 / 1e6 = 0.0375
    const result = calculateCost(usage, 'L3');
    expect(result).toBeCloseTo(0.0375, 6);
  });

  it('handles escalation tier format (L2->L3)', () => {
    const usage = { input_tokens: 1000, output_tokens: 100 };
    // Should use L2 rates (the base tier)
    const result = calculateCost(usage, 'L2->L3');
    const expectedL2 = (1000 * 0.25 + 100 * 1.25) / 1e6;
    expect(result).toBeCloseTo(expectedL2, 6);
  });

  it('defaults to L3 for unknown tier', () => {
    const usage = { input_tokens: 1000, output_tokens: 100 };
    const result = calculateCost(usage, 'UNKNOWN');
    const expectedL3 = (1000 * 3 + 100 * 15) / 1e6;
    expect(result).toBeCloseTo(expectedL3, 6);
  });

  it('handles alternate field names', () => {
    const usage = {
      input_tokens: 1000,
      output_tokens: 100,
      cache_read_tokens: 500,
      cache_write_tokens: 200,
    };
    // L3: (1000*3 + 100*15 + 500*0.3 + 200*3.75) / 1e6
    const expected = (3000 + 1500 + 150 + 750) / 1e6;
    const result = calculateCost(usage, 'L3');
    expect(result).toBeCloseTo(expected, 6);
  });
});

describe('normalizeTurn', () => {
  it('preserves existing turn_id', () => {
    const turn = { turn_id: 'my-turn' };
    const result = normalizeTurn(turn, 5);
    expect(result.turn_id).toBe('my-turn');
  });

  it('generates turn_id from index if missing', () => {
    const turn = {};
    const result = normalizeTurn(turn, 3);
    expect(result.turn_id).toBe('turn_3');
  });

  it('normalizes user_message from message field', () => {
    const turn = { message: 'hello' };
    const result = normalizeTurn(turn, 0);
    expect(result.user_message).toBe('hello');
  });

  it('normalizes response_text from output field', () => {
    const turn = { output: '{"t":"voice","text":"hi"}' };
    const result = normalizeTurn(turn, 0);
    expect(result.response_text).toBe('{"t":"voice","text":"hi"}');
  });

  it('creates llm_calls from eval turn format', () => {
    const turn = {
      tier: 'L2',
      model: 'claude-3-haiku',
      ttc_ms: 500,
      system_prompt: 'You are helpful',
      output: '{"t":"voice"}',
      input_tokens: 100,
      output_tokens: 50,
    };
    const result = normalizeTurn(turn, 0);
    expect(result.llm_calls).toHaveLength(1);
    expect(result.llm_calls[0].tier).toBe('L2');
    expect(result.llm_calls[0].model).toBe('claude-3-haiku');
    expect(result.llm_calls[0].latency_ms).toBe(500);
    expect(result.llm_calls[0].prompt).toBe('You are helpful');
    expect(result.llm_calls[0].usage.input_tokens).toBe(100);
  });

  it('preserves existing llm_calls array', () => {
    const turn = {
      llm_calls: [
        { call_id: 'existing', tier: 'L3' },
      ],
    };
    const result = normalizeTurn(turn, 0);
    expect(result.llm_calls[0].call_id).toBe('existing');
  });

  it('parses primitives_emitted from output if missing', () => {
    const turn = {
      output: '{"t":"entity.create","id":"foo"}\n{"t":"voice","text":"done"}',
    };
    const result = normalizeTurn(turn, 0);
    expect(result.primitives_emitted).toHaveLength(2);
    expect(result.primitives_emitted[0].type).toBe('entity.create');
  });

  it('preserves eval-specific fields', () => {
    const turn = {
      score: { composite: 0.9, validity: 1.0 },
      expected_tier: 'L2',
      classified_tier: 'L3',
      notes: 'Test note',
    };
    const result = normalizeTurn(turn, 0);
    expect(result.score.composite).toBe(0.9);
    expect(result.expected_tier).toBe('L2');
    expect(result.classified_tier).toBe('L3');
    expect(result.notes).toBe('Test note');
  });
});
