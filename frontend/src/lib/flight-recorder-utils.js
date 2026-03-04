/**
 * Flight Recorder Utility Functions
 *
 * Pure utility functions for the flight recorder UI.
 * Extracted for testability.
 */

// Cost rates per 1M tokens - by model
export const MODEL_RATES = {
  // Sonnet 4.5
  'claude-sonnet-4-5-20250929': { in: 3, out: 15, cache_read: 0.3, cache_write: 3.75 },
  // Opus 4.5
  'claude-opus-4-5-20251101': { in: 15, out: 75, cache_read: 1.5, cache_write: 18.75 },
  // Haiku 3.5
  'claude-3-5-haiku-20241022': { in: 0.8, out: 4, cache_read: 0.08, cache_write: 1 },
  // Legacy tier-based fallbacks
  L4: { in: 15, out: 75, cache_read: 1.5, cache_write: 18.75 },
  L3: { in: 3, out: 15, cache_read: 0.3, cache_write: 3.75 },
  L2: { in: 0.25, out: 1.25, cache_read: 0.03, cache_write: 0.3125 },
};

// Alias for backwards compatibility
export const COST_RATES = MODEL_RATES;

/**
 * Calculate cost in USD based on token usage and model/tier.
 *
 * @param {Object|null} usage - Token usage object with input_tokens, output_tokens, cache_read, cache_creation
 * @param {string} tierOrModel - Model ID or tier (L2, L3, L4)
 * @returns {number} Cost in USD
 */
export function calculateCost(usage, tierOrModel) {
  if (!usage) return 0;
  // Try model ID first, then tier fallback
  const key = tierOrModel?.split('->')[0] || 'L3';
  const r = MODEL_RATES[key] || MODEL_RATES.L3;
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
      // Handle { type, input } format (eval format)
      if (tc.type && tc.input) return { t: tc.type, ...tc.input };
      // Handle { name, input } format (telemetry API format)
      if (tc.name && tc.input) {
        const input = tc.input;
        if (tc.name === 'mutate_entity') {
          const action = input.action;
          if (action === 'create') {
            return { t: 'entity.create', id: input.id, parent: input.parent, display: input.display, p: input.props };
          } else if (action === 'update') {
            return { t: 'entity.update', ref: input.ref, p: input.props };
          } else if (action === 'remove') {
            return { t: 'entity.remove', ref: input.ref };
          }
        } else if (tc.name === 'voice') {
          return { t: 'voice', text: input.text };
        } else if (tc.name === 'set_relationship') {
          return { t: 'rel.set', ...input };
        }
        return { t: tc.name, ...input };
      }
      // Handle already normalized format
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

// ══════════════════════════════════════════════════════════════════════════════
// REPLAY FEATURES
// ══════════════════════════════════════════════════════════════════════════════

/**
 * Calculate delay for playback based on speed multiplier.
 *
 * @param {number|null} ms - Original delay in milliseconds
 * @param {number} speed - Speed multiplier (1=realtime, 2=2x, 5=5x, 0=instant)
 * @returns {number} Adjusted delay in milliseconds
 */
export function calculateDelay(ms, speed) {
  if (ms == null) return 0;
  if (speed === 0) return 0;
  return Math.round(ms / speed);
}

/**
 * Get mutation tag info for a tool call.
 *
 * @param {Object|null} tc - Tool call object
 * @returns {Object|null} { type, label, id?, from?, to? }
 */
export function getMutationTag(tc) {
  if (!tc) return null;

  // Normalize format
  let t = tc.t;
  let data = tc;
  if (tc.type && tc.input) {
    t = tc.type;
    data = tc.input;
  } else if (tc.name && tc.input) {
    // Handle API format (name/input)
    const input = tc.input;
    if (tc.name === 'mutate_entity') {
      const action = input.action;
      if (action === 'create') {
        t = 'entity.create';
        data = input;
      } else if (action === 'update') {
        t = 'entity.update';
        data = { ref: input.ref, ...input };
      } else if (action === 'remove') {
        t = 'entity.remove';
        data = { ref: input.ref };
      }
    } else if (tc.name === 'voice') {
      t = 'voice';
      data = input;
    } else if (tc.name === 'set_relationship') {
      t = 'rel.set';
      data = input;
    } else {
      t = tc.name;
      data = input;
    }
  }

  if (!t) return null;

  // entity.create / entity.update / entity.remove
  if (t === 'entity.create') {
    return { type: 'create', label: 'create', id: data.id };
  }
  if (t === 'entity.update') {
    return { type: 'update', label: 'update', id: data.ref };
  }
  if (t === 'entity.remove') {
    return { type: 'remove', label: 'remove', id: data.ref };
  }

  // relationship events
  if (t.startsWith('relationship.') || t === 'set_relationship') {
    return { type: 'rel', label: 'rel', from: data.from, to: data.to };
  }

  // meta events
  if (t.startsWith('meta.')) {
    return { type: 'meta', label: 'meta' };
  }

  return { type: 'other', label: t.split('.').pop() || 'call' };
}

/**
 * Format cost label for display.
 *
 * @param {number} turnCost - Cost for this turn
 * @param {number} cumulativeCost - Total cost up to this turn
 * @param {number} cachePercent - Cache hit percentage (0-100)
 * @returns {string} Formatted cost label
 */
export function formatCostLabel(turnCost, cumulativeCost, cachePercent) {
  let label = `$${turnCost.toFixed(4)}`;
  if (cachePercent > 0) {
    label += ` (${cachePercent}% cached)`;
  }
  label += ` · Σ$${cumulativeCost.toFixed(4)}`;
  return label;
}

/**
 * Build sorted stream events from a turn for replay simulation.
 *
 * @param {Object} turn - Turn object with tool_calls, text_blocks, ttfc_ms, ttc_ms
 * @returns {Array} Sorted events: { type: 'mutation'|'voice', ts, data?, text? }
 */
export function buildStreamEvents(turn) {
  const events = [];
  const toolCalls = turn.tool_calls || [];
  const textBlocks = turn.text_blocks || [];
  const ttfc = turn.ttfc_ms ?? 500;
  const ttc = turn.ttc_ms ?? 2000;

  // Check if we have real timestamps
  const hasTimestamps =
    (toolCalls.length > 0 && toolCalls[0].timestamp_ms !== undefined) ||
    (textBlocks.length > 0 && typeof textBlocks[0] === 'object' && textBlocks[0].timestamp_ms !== undefined);

  // Helper to check if a tool call is a voice call
  const isVoiceCall = (tc) => tc.name === 'voice' || tc.t === 'voice';
  const getVoiceText = (tc) => tc.input?.text || tc.text || '';

  if (hasTimestamps) {
    // Use real timestamps
    for (const tc of toolCalls) {
      if (isVoiceCall(tc)) {
        events.push({
          type: 'voice',
          ts: tc.timestamp_ms || 0,
          text: getVoiceText(tc),
        });
      } else {
        events.push({
          type: 'mutation',
          ts: tc.timestamp_ms || 0,
          data: tc,
        });
      }
    }
    for (const tb of textBlocks) {
      const text = typeof tb === 'string' ? tb : tb.text;
      const ts = typeof tb === 'object' ? tb.timestamp_ms || 0 : 0;
      events.push({
        type: 'voice',
        ts,
        text,
      });
    }
  } else {
    // Assign heuristic timestamps based on ttfc/ttc
    const streamTime = ttc - ttfc;
    const totalItems = toolCalls.length + textBlocks.length;
    const perItem = totalItems > 0 ? streamTime / totalItems : 0;

    let currentTs = ttfc;
    for (const tc of toolCalls) {
      if (isVoiceCall(tc)) {
        events.push({
          type: 'voice',
          ts: currentTs,
          text: getVoiceText(tc),
        });
      } else {
        events.push({
          type: 'mutation',
          ts: currentTs,
          data: tc,
        });
      }
      currentTs += perItem;
    }
    for (const tb of textBlocks) {
      const text = typeof tb === 'string' ? tb : tb.text;
      events.push({
        type: 'voice',
        ts: currentTs,
        text,
      });
      currentTs += perItem;
    }
  }

  // Sort by timestamp
  events.sort((a, b) => a.ts - b.ts);
  return events;
}

/**
 * Calculate progress percentage for the timeline.
 *
 * @param {number} currentTurn - Current turn index (0-based, -1 if not started)
 * @param {number} totalTurns - Total number of turns
 * @returns {number} Percentage (0-100)
 */
export function getProgressPercent(currentTurn, totalTurns) {
  if (totalTurns === 0) return 0;
  if (currentTurn < 0) return 0;
  return Math.round(((currentTurn + 1) / totalTurns) * 100);
}
