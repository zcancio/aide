/**
 * Flight Recorder Utility Functions
 * Extracted for testability - used by flight-recorder.html
 */

/**
 * Parse JSONL events from output string
 * @param {string} output - Raw JSONL output from LLM
 * @returns {Array} Parsed event objects
 */
export function parseEvents(output) {
  if (!output) return [];
  const events = [];
  for (const line of output.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('`')) continue;
    try {
      events.push(JSON.parse(trimmed));
    } catch {
      // Skip invalid JSON lines
    }
  }
  return events;
}

/**
 * Build hierarchical entity tree from snapshot
 * @param {Object} entities - Entity map from snapshot
 * @param {Object|null} removedEntities - Entities that were removed (for diff display)
 * @returns {Array} Flat array of entities with depth info
 */
export function buildTree(entities, removedEntities) {
  if (!entities) return [];

  const merged = { ...entities };
  if (removedEntities) {
    for (const [id, e] of Object.entries(removedEntities)) {
      if (!merged[id]) merged[id] = { ...e, _removed: true };
    }
  }

  const all = Object.values(merged).filter(e => e && e.id);
  const allIds = new Set(all.map(e => e.id));
  allIds.add("root");

  const children = {};
  all.forEach(e => {
    const p = e.parent || "root";
    (children[p] = children[p] || []).push(e);
  });

  // Sort: non-removed first
  for (const p of Object.keys(children)) {
    children[p].sort((a, b) => (a._removed ? 1 : 0) - (b._removed ? 1 : 0));
  }

  const out = [];
  const visited = new Set();

  const walk = (pid, depth) => {
    (children[pid] || []).forEach(c => {
      visited.add(c.id);
      out.push({ ...c, depth });
      walk(c.id, depth + 1);
    });
  };

  walk("root", 0);

  // Find orphans (entities whose parent doesn't exist)
  const orphans = all.filter(e => !visited.has(e.id) && !allIds.has(e.parent || "root"));
  orphans.forEach(o => out.push({ ...o, depth: 0, _orphan: true }));

  return out;
}

/**
 * Compute entity diff between two snapshots
 * @param {Object} before - Entities before the turn
 * @param {Object} after - Entities after the turn
 * @returns {Object} Diff result with add, rem, mod arrays and details
 */
export function computeDiff(before, after) {
  const bk = new Set(Object.keys(before || {}));
  const ak = new Set(Object.keys(after || {}));

  const add = [...ak].filter(k => !bk.has(k));
  const rem = [...bk].filter(k => !ak.has(k));
  const mod = [];
  const modDetails = {};
  const moved = {};

  for (const k of ak) {
    if (!bk.has(k)) continue;

    const bp = JSON.stringify((before[k]?.props || before[k]?.p || {}));
    const ap = JSON.stringify((after[k]?.props || after[k]?.p || {}));
    const bParent = before[k]?.parent;
    const aParent = after[k]?.parent;
    const parentChanged = bParent !== aParent;

    if (bp !== ap || parentChanged) {
      mod.push(k);
      const bObj = before[k]?.props || before[k]?.p || {};
      const aObj = after[k]?.props || after[k]?.p || {};
      const changed = [];
      const allKeys = new Set([...Object.keys(bObj), ...Object.keys(aObj)]);

      for (const pk of allKeys) {
        if (JSON.stringify(bObj[pk]) !== JSON.stringify(aObj[pk])) {
          changed.push(
            bObj[pk] === undefined ? `+${pk}` :
            aObj[pk] === undefined ? `-${pk}` :
            pk
          );
        }
      }

      if (parentChanged) {
        changed.push(`parent: ${bParent}→${aParent}`);
        moved[k] = { from: bParent, to: aParent };
      }

      modDetails[k] = changed;
    }
  }

  return { add, rem, mod, modDetails, moved };
}

/**
 * Calculate cost from token usage
 * @param {Object} usage - Token usage object
 * @param {string} tier - LLM tier (L2, L3, L4)
 * @returns {number} Cost in dollars
 */
export function calculateCost(usage, tier) {
  if (!usage) return 0;

  // Per-million token rates
  const rates = {
    L4: { in: 15, out: 75, cache_read: 1.5, cache_write: 18.75 },
    L3: { in: 3, out: 15, cache_read: 0.3, cache_write: 3.75 },
    L2: { in: 0.25, out: 1.25, cache_read: 0.025, cache_write: 0.3125 },
  };

  // Handle escalation format like "L2->L3"
  const baseTier = tier?.split("->")[0] || "L3";
  const r = rates[baseTier] || rates.L3;

  const input = usage.input_tokens || 0;
  const output = usage.output_tokens || 0;
  const cacheRead = usage.cache_read || usage.cache_read_tokens || 0;
  const cacheWrite = usage.cache_creation || usage.cache_write_tokens || 0;

  return (input * r.in + output * r.out + cacheRead * r.cache_read + cacheWrite * r.cache_write) / 1e6;
}

/**
 * Normalize turn data from various formats (API vs eval golden)
 * @param {Object} turn - Raw turn object
 * @param {number} index - Turn index
 * @returns {Object} Normalized turn object
 */
export function normalizeTurn(turn, index) {
  return {
    turn_id: turn.turn_id || `turn_${index}`,
    turn_index: turn.turn_index ?? index,
    timestamp: turn.timestamp || new Date().toISOString(),
    source: turn.source || 'file',
    user_message: turn.user_message || turn.message || '',
    response_text: turn.response_text || turn.output || '',
    llm_calls: turn.llm_calls || [{
      call_id: `call_${index}`,
      shadow: false,
      model: turn.model || 'unknown',
      tier: turn.tier || 'L3',
      latency_ms: turn.ttc_ms || 0,
      prompt: turn.system_prompt || '',
      response: turn.output || '',
      usage: {
        input_tokens: turn.input_tokens || 0,
        output_tokens: turn.output_tokens || 0,
        cache_read: turn.cache_read || 0,
        cache_creation: turn.cache_creation || 0,
      }
    }],
    primitives_emitted: turn.primitives_emitted || parseEvents(turn.output).map(e => ({ type: e.t, payload: e })),
    primitives_applied: turn.primitives_applied || 0,
    total_latency_ms: turn.total_latency_ms || turn.ttc_ms || 0,
    snapshot_before: turn.snapshot_before || null,
    snapshot_after: turn.snapshot_after || null,
    // Eval-specific fields
    score: turn.score,
    expected_tier: turn.expected_tier,
    classified_tier: turn.classified_tier,
    notes: turn.notes,
  };
}
