/**
 * Flight Recorder Utility Functions
 *
 * Pure utility functions for the flight recorder UI.
 * Extracted for testability.
 */

// Cost rates per 1M tokens
export const COST_RATES = {
  L4: { in: 15, out: 75, cache_read: 1.5, cache_write: 18.75 },
  L3: { in: 3, out: 15, cache_read: 0.3, cache_write: 3.75 },
  L2: { in: 0.25, out: 1.25, cache_read: 0.03, cache_write: 0.3125 },
};

/**
 * Calculate cost in USD based on token usage and tier.
 *
 * @param {Object|null} usage - Token usage object with input_tokens, output_tokens, cache_read, cache_creation
 * @param {string} tier - Pricing tier (L2, L3, L4, or with arrow like "L3->L4")
 * @returns {number} Cost in USD
 */
export function calculateCost(usage, tier) {
  if (!usage) return 0;
  const tierKey = tier?.split('->')[0] || 'L3';
  const r = COST_RATES[tierKey] || COST_RATES.L3;
  return (
    ((usage.input_tokens || 0) * r.in) / 1e6 +
    ((usage.output_tokens || 0) * r.out) / 1e6 +
    ((usage.cache_read || 0) * r.cache_read) / 1e6 +
    ((usage.cache_creation || 0) * r.cache_write) / 1e6
  );
}

/**
 * Parse tool calls into a normalized event array.
 *
 * Handles both formats:
 * - { type: 'entity.create', input: { id: 'e1', ... } }
 * - { t: 'entity.create', id: 'e1', ... }
 *
 * @param {Array|null} toolCalls - Array of tool calls
 * @returns {Array} Normalized events with { t, ...rest }
 */
export function parseToolCalls(toolCalls) {
  if (!toolCalls || !Array.isArray(toolCalls)) return [];
  return toolCalls
    .map((tc) => {
      if (!tc) return null;
      if (tc.type && tc.input) return { t: tc.type, ...tc.input };
      if (tc.t) return tc;
      return tc;
    })
    .filter(Boolean);
}

/**
 * Build an entity tree from a flat entities object.
 *
 * @param {Object|null} ents - Entities object { id: { id, parent, display, props } }
 * @param {Object|null} removedEnts - Removed entities to include with _removed flag
 * @returns {Array} Tree nodes with { ...entity, depth, _removed?, _orphan? }
 */
export function mkTree(ents, removedEnts) {
  if (!ents) return [];
  const merged = { ...ents };
  if (removedEnts) {
    for (const [id, e] of Object.entries(removedEnts)) {
      if (!merged[id]) merged[id] = { ...e, _removed: true };
    }
  }
  const all = Object.values(merged).filter((e) => e && e.id);
  const allIds = new Set(all.map((e) => e.id));
  allIds.add('root');
  const ch = {};
  all.forEach((e) => {
    const p = e.parent || 'root';
    (ch[p] = ch[p] || []).push(e);
  });
  for (const p of Object.keys(ch)) {
    ch[p].sort((a, b) => (a._removed ? 1 : 0) - (b._removed ? 1 : 0));
  }
  const out = [];
  const visited = new Set();
  const walk = (pid, d) => {
    (ch[pid] || []).forEach((c) => {
      visited.add(c.id);
      out.push({ ...c, depth: d });
      walk(c.id, d + 1);
    });
  };
  walk('root', 0);
  const orphans = all.filter((e) => !visited.has(e.id) && !allIds.has(e.parent || 'root'));
  if (orphans.length > 0) {
    orphans.forEach((o) => {
      out.push({ ...o, depth: 0, _orphan: true });
    });
  }
  return out;
}

/**
 * Compute diff between two entity snapshots.
 *
 * @param {Object|null} b - Before snapshot entities
 * @param {Object|null} a - After snapshot entities
 * @returns {Object} { add, rem, mod, modDetails, moved }
 */
export function eDiff(b, a) {
  const bk = new Set(Object.keys(b || {}));
  const ak = new Set(Object.keys(a || {}));
  const add = [...ak].filter((k) => !bk.has(k));
  const rem = [...bk].filter((k) => !ak.has(k));
  const mod = [];
  const modDetails = {};
  const moved = {};
  for (const k of ak) {
    if (!bk.has(k)) continue;
    const bp = JSON.stringify(b[k]?.props || b[k]?.p || {});
    const ap = JSON.stringify(a[k]?.props || a[k]?.p || {});
    const bParent = b[k]?.parent;
    const aParent = a[k]?.parent;
    const parentChanged = bParent !== aParent;
    if (bp !== ap || parentChanged) {
      mod.push(k);
      const bObj = b[k]?.props || b[k]?.p || {};
      const aObj = a[k]?.props || a[k]?.p || {};
      const changed = [];
      const allKeys = new Set([...Object.keys(bObj), ...Object.keys(aObj)]);
      for (const pk of allKeys) {
        if (JSON.stringify(bObj[pk]) !== JSON.stringify(aObj[pk])) {
          changed.push(
            bObj[pk] === undefined
              ? `+${pk}`
              : aObj[pk] === undefined
                ? `-${pk}`
                : `${pk}: ${JSON.stringify(bObj[pk])}->${JSON.stringify(aObj[pk])}`
          );
        }
      }
      if (parentChanged) {
        changed.push(`parent: ${bParent}->${aParent}`);
        moved[k] = { from: bParent, to: aParent };
      }
      modDetails[k] = changed;
    }
  }
  return { add, rem, mod, modDetails, moved };
}

/**
 * Build cumulative snapshot from turns up to a specific index.
 *
 * @param {Array} turns - Array of turn objects with tool_calls
 * @param {number} upToIndex - Build snapshot including this turn index
 * @returns {Object} { meta: {}, entities: {} }
 */
export function buildSnapshot(turns, upToIndex) {
  let snapshot = { meta: {}, entities: {} };
  for (let i = 0; i <= upToIndex && i < turns.length; i++) {
    const turn = turns[i];
    const events = parseToolCalls(turn.tool_calls);
    for (const evt of events) {
      if (evt.t === 'meta.set' || evt.t === 'meta.update') {
        snapshot.meta = { ...snapshot.meta, ...evt.p };
      } else if (evt.t === 'entity.create') {
        snapshot.entities[evt.id] = {
          id: evt.id,
          parent: evt.parent || 'root',
          display: evt.display,
          props: evt.p || {},
        };
      } else if (evt.t === 'entity.update') {
        if (snapshot.entities[evt.ref]) {
          snapshot.entities[evt.ref].props = {
            ...snapshot.entities[evt.ref].props,
            ...evt.p,
          };
        }
      } else if (evt.t === 'entity.remove') {
        delete snapshot.entities[evt.ref];
      }
    }
  }
  return snapshot;
}
