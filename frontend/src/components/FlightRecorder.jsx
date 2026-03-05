/**
 * FlightRecorder.jsx - Unified flight recorder UI
 *
 * Loads telemetry from API or file upload, displays:
 * - 6 view tabs (Rendered, Raw Output, Before/After, Entity Tree, Prompt, Cost)
 * - Metrics panel (routing, latency, tokens, cost)
 * - Timeline with turn markers and playback
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { fetchTelemetry, fetchAides } from '../lib/api.js';
import {
  calculateCost,
  parseToolCalls,
  mkTree,
  eDiff,
  buildSnapshot,
  COST_RATES,
  calculateDelay,
  getMutationTag,
  formatCostLabel,
  buildStreamEvents,
  getProgressPercent,
} from '../lib/flight-recorder-utils.js';
import { renderHtml, RENDERER_CSS } from '../lib/display/index.js';
import '../styles/flight-recorder.css';

// Tier colors
const TC = {
  L2: { bg: '#0c4a6e', tx: '#7dd3fc', bd: '#0369a1', lb: 'L2' },
  L3: { bg: '#06b6d4', tx: '#cffafe', bd: '#0891b2', lb: 'L3' },
  L4: { bg: '#7c3aed', tx: '#e9d5ff', bd: '#6d28d9', lb: 'L4' },
};

// Event type colors
const EC = {
  'entity.create': { bg: '#064e3b', tx: '#6ee7b7', bd: '#047857' },
  'entity.update': { bg: '#1e3a5f', tx: '#93c5fd', bd: '#2563eb' },
  'entity.remove': { bg: '#4c0519', tx: '#fda4af', bd: '#be123c' },
  'meta.set': { bg: '#422006', tx: '#fdba74', bd: '#c2410c' },
  'meta.update': { bg: '#422006', tx: '#fdba74', bd: '#c2410c' },
  voice: { bg: '#1a2e05', tx: '#bef264', bd: '#4d7c0f' },
  'view.create': { bg: '#3b1f63', tx: '#c4b5fd', bd: '#7c3aed' },
  'block.set': { bg: '#1e293b', tx: '#94a3b8', bd: '#334155' },
  'collection.create': { bg: '#064e3b', tx: '#6ee7b7', bd: '#047857' },
};

function TierBadge({ tier, small }) {
  const c = TC[tier] || TC.L3;
  return (
    <span
      className={`fr-tier-badge ${small ? 'fr-tier-badge--small' : ''}`}
      style={{ background: c.bg, borderColor: c.bd, color: c.tx }}
    >
      {c.lb}
    </span>
  );
}

function EventPill({ event }) {
  const c = EC[event.t] || { bg: '#1e293b', tx: '#94a3b8', bd: '#334155' };
  return (
    <span
      className="fr-event-pill"
      style={{ background: c.bg, borderColor: c.bd, color: c.tx }}
    >
      <b>{event.t}</b>
      {(event.id || event.ref) && ` ${event.id || event.ref}`}
    </span>
  );
}

export default function FlightRecorder() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialAideId = searchParams.get('aide_id') || '';

  // Try to restore data from localStorage on initial load
  const [data, setData] = useState(() => {
    try {
      const saved = localStorage.getItem('FR_DATA');
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [idx, setIdx] = useState(() => {
    try {
      const saved = localStorage.getItem('FR_IDX');
      return saved ? parseInt(saved, 10) : 0;
    } catch {
      return 0;
    }
  });
  const [tab, setTab] = useState('rendered');
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(2); // 1=realtime, 2=2x, 5=5x, 0=instant
  const [streaming, setStreaming] = useState(false); // true during turn animation
  const [streamEvents, setStreamEvents] = useState([]); // events shown so far in current turn
  const [showTyping, setShowTyping] = useState(false);
  const [aideIdInput, setAideIdInput] = useState(initialAideId);
  const [aides, setAides] = useState([]);
  const fileRef = useRef(null);
  const previewRef = useRef(null);
  const shadowRef = useRef(null);
  const playTimerRef = useRef(null);

  // Persist data and idx to localStorage when they change
  useEffect(() => {
    if (data) {
      try {
        localStorage.setItem('FR_DATA', JSON.stringify(data));
      } catch {
        // localStorage full or unavailable - ignore
      }
    }
  }, [data]);

  useEffect(() => {
    try {
      localStorage.setItem('FR_IDX', String(idx));
    } catch {
      // ignore
    }
  }, [idx]);

  const turns = useMemo(() => data?.turns || [], [data]);
  // N includes turn 0 (initial empty state) + all actual turns
  const N = turns.length + 1;
  // Turn 0 is synthetic (empty state), turns 1+ map to actual turns
  const actualTurnIdx = idx - 1;
  const t = actualTurnIdx >= 0 ? turns[actualTurnIdx] : {};
  const isTurn0 = idx === 0;

  // Build snapshots for current turn
  // Turn 0: before=empty, after=empty
  // Turn 1+: before=snapshot up to prev turn, after=snapshot up to current turn
  const snapshotBefore = useMemo(
    () => (actualTurnIdx > 0 ? buildSnapshot(turns, actualTurnIdx - 1) : { meta: {}, entities: {} }),
    [turns, actualTurnIdx]
  );
  const snapshotAfter = useMemo(
    () => (actualTurnIdx >= 0 ? buildSnapshot(turns, actualTurnIdx) : { meta: {}, entities: {} }),
    [turns, actualTurnIdx]
  );
  const diff = useMemo(
    () => eDiff(snapshotBefore.entities, snapshotAfter.entities),
    [snapshotBefore, snapshotAfter]
  );
  const removedEnts = useMemo(() => {
    if (!diff.rem.length) return null;
    const out = {};
    for (const id of diff.rem) {
      if (snapshotBefore.entities[id]) out[id] = snapshotBefore.entities[id];
    }
    return out;
  }, [diff.rem, snapshotBefore]);
  const tree = useMemo(
    () => mkTree(snapshotAfter.entities, removedEnts),
    [snapshotAfter, removedEnts]
  );
  const events = useMemo(() => parseToolCalls(t.tool_calls), [t.tool_calls]);

  // Build streaming snapshot - applies mutations incrementally as they stream in
  const streamingSnapshot = useMemo(() => {
    if (!streaming) return null;

    // Start from state before current turn, but don't copy meta until we have entities
    // This ensures title doesn't show until first entity.create
    const snapshot = {
      meta: {},
      entities: { ...snapshotBefore.entities },
    };

    // Track if we've seen any entity.create in the stream
    let hasCreatedEntity = Object.keys(snapshotBefore.entities).length > 0;

    // Apply each streamed mutation
    for (const evt of streamEvents) {
      if (evt.type !== 'mutation') continue;
      const tc = evt.data;

      // Normalize the tool call format
      let eventType, input;
      if (tc.t) {
        eventType = tc.t;
        input = tc;
      } else if (tc.type && tc.input) {
        eventType = tc.type;
        input = tc.input;
      } else if (tc.name && tc.input) {
        input = tc.input;
        if (tc.name === 'mutate_entity') {
          const action = input.action;
          if (action === 'create') eventType = 'entity.create';
          else if (action === 'update') eventType = 'entity.update';
          else if (action === 'remove') eventType = 'entity.remove';
        } else {
          eventType = tc.name;
        }
      }

      if (!eventType) continue;

      // Apply the mutation
      if (eventType === 'entity.create') {
        hasCreatedEntity = true;
        snapshot.entities[input.id] = {
          id: input.id,
          parent: input.parent || 'root',
          display: input.display,
          props: input.props || input.p || {},
        };
      } else if (eventType === 'entity.update') {
        const ref = input.ref;
        if (snapshot.entities[ref]) {
          snapshot.entities[ref] = {
            ...snapshot.entities[ref],
            props: {
              ...snapshot.entities[ref].props,
              ...(input.props || input.p || {}),
            },
          };
        }
      } else if (eventType === 'entity.remove') {
        delete snapshot.entities[input.ref];
      } else if (eventType === 'meta.set' || eventType === 'meta.update') {
        // Only apply meta after we have entities (or had them before)
        if (hasCreatedEntity) {
          snapshot.meta = { ...snapshot.meta, ...(input.p || input.props || {}) };
        }
      }
    }

    // If we have entities, include previous meta as base
    if (hasCreatedEntity) {
      snapshot.meta = { ...snapshotBefore.meta, ...snapshot.meta };
    }

    return snapshot;
  }, [streaming, streamEvents, snapshotBefore]);

  // Calculate cumulative cost (turn 0 has no cost)
  const cumulativeCost = useMemo(() => {
    let total = 0;
    for (let i = 0; i <= actualTurnIdx && i < turns.length; i++) {
      total += calculateCost(turns[i].usage, turns[i].model || turns[i].tier);
    }
    return total;
  }, [turns, actualTurnIdx]);

  const turnCost = calculateCost(t.usage, t.model || t.tier);

  // Load aides list on mount for picker
  useEffect(() => {
    fetchAides().then(({ data: aidesData }) => {
      if (aidesData) setAides(aidesData);
    });
  }, []);

  // Load from API
  const loadFromAPI = useCallback(async (aideId) => {
    if (!aideId) return;
    setLoading(true);
    setError(null);
    const { data: telemetry, error: err } = await fetchTelemetry(aideId);
    if (err) {
      setError(err);
    } else if (telemetry?.turns?.length) {
      setData(telemetry);
      setIdx(0);
      setTab('rendered');
      setSearchParams({ aide_id: aideId }, { replace: true });
    } else {
      setError('No telemetry data found');
    }
    setLoading(false);
  }, [setSearchParams]);

  // Load from file
  const loadFromFile = useCallback((file) => {
    const reader = new FileReader();
    reader.onload = (ev) => {
      try {
        const json = JSON.parse(ev.target.result);
        let loaded;
        if (json.turns) {
          loaded = json;
        } else if (json.results?.length) {
          const pick = json.results[0];
          loaded = {
            aide_id: pick.aide_id || 'loaded',
            name: pick.name || pick.scenario || 'Loaded File',
            timestamp: pick.timestamp || new Date().toISOString(),
            turns: pick.turns || [],
            final_snapshot: pick.final_snapshot,
          };
        }
        if (loaded?.turns?.length) {
          setData(loaded);
          setIdx(0);
          setTab('rendered');
          setError(null);
        } else {
          setError('Invalid file format: no turns found');
        }
      } catch {
        setError('Failed to parse JSON file');
      }
    };
    reader.readAsText(file);
  }, []);

  // Reset shadow ref when data changes or tab switches away from rendered
  useEffect(() => {
    if (tab !== 'rendered') {
      shadowRef.current = null;
    }
  }, [tab]);

  useEffect(() => {
    shadowRef.current = null;
  }, [data]);

  // Initialize Shadow DOM for preview (runs when data loads or tab changes to 'rendered')
  useEffect(() => {
    if (!data || tab !== 'rendered' || !previewRef.current || shadowRef.current) return;
    const shadow = previewRef.current.attachShadow({ mode: 'open' });
    shadowRef.current = shadow;
    const style = document.createElement('style');
    // Add dark theme overrides after the renderer CSS
    const darkThemeCSS = `
      .aide-preview-content {
        background: #1a1f1a;
        color: #e8e6e3;
        min-height: 100%;
        padding: 16px;
      }
      .aide-page { background: transparent; }
      .aide-heading { color: #e8e6e3; }
      .aide-text { color: #c4c2bf; }
      .aide-section { border-color: #3a3f3a; }
      .aide-section__title { color: #e8e6e3; }
      .aide-card { background: #252a25; border-color: #3a3f3a; }
      .aide-card__title { color: #e8e6e3; }
      .aide-card__label { color: #8a8a8a; }
      .aide-metric { background: #252a25; border-color: #3a3f3a; }
      .aide-metric__label { color: #8a8a8a; }
      .aide-metric__value { color: #e8e6e3; }
      .aide-table { background: #252a25; }
      .aide-table__th { background: #1a1f1a; color: #8a8a8a; border-color: #3a3f3a; }
      .aide-table__td { border-color: #3a3f3a; color: #c4c2bf; }
      .aide-checklist { background: #252a25; }
      .aide-checklist__label { color: #c4c2bf; }
      .aide-checklist__summary { color: #8a8a8a; }
      .aide-list__item { border-color: #3a3f3a; color: #c4c2bf; }
      .aide-empty { color: #6a6a6a; }
    `;
    style.textContent = RENDERER_CSS + darkThemeCSS;
    shadow.appendChild(style);
    const content = document.createElement('div');
    content.className = 'aide-preview-content';
    shadow.appendChild(content);
  }, [data, tab]);

  // Update preview when turn changes or streaming events update
  useEffect(() => {
    if (!shadowRef.current || !data || N === 0 || tab !== 'rendered') return;
    const content = shadowRef.current.querySelector('.aide-preview-content');
    if (!content) return;

    // Use streaming snapshot during replay, otherwise use completed snapshot
    let snapshot;
    if (streaming && streamingSnapshot) {
      snapshot = streamingSnapshot;
    } else if (idx === N - 1 && data.final_snapshot) {
      snapshot = data.final_snapshot;
    } else {
      snapshot = snapshotAfter;
    }

    // Convert snapshot to renderHtml format (needs rootIds)
    const entities = snapshot.entities || {};
    const rootIds = Object.keys(entities).filter(
      (id) => !entities[id].parent || entities[id].parent === 'root'
    );
    const store = { entities, rootIds, meta: snapshot.meta || {} };
    const html = renderHtml(store);
    content.innerHTML = html;
  }, [idx, data, N, tab, snapshotAfter, streaming, streamingSnapshot]);

  // Auto-load if aide_id in URL
  useEffect(() => {
    if (initialAideId && !data) {
      loadFromAPI(initialAideId);
    }
  }, [initialAideId, data, loadFromAPI]);

  // Streaming playback - simulates real-time turn execution
  useEffect(() => {
    if (!playing || N === 0) return;

    let cancelled = false;

    const playTurn = async (turnIdx) => {
      if (cancelled || turnIdx >= N) {
        setPlaying(false);
        return;
      }

      setIdx(turnIdx);

      // Turn 0 is the initial empty state - brief pause then continue
      if (turnIdx === 0) {
        await new Promise((r) => {
          playTimerRef.current = setTimeout(r, calculateDelay(300, speed));
        });
        if (cancelled) return;
        playTurn(1);
        return;
      }

      // Actual turns (turnIdx >= 1 maps to turns[turnIdx - 1])
      const turn = turns[turnIdx - 1];
      if (!turn) {
        setPlaying(false);
        return;
      }

      setStreaming(true);
      setStreamEvents([]);

      // Show typing indicator during TTFC
      setShowTyping(true);
      const ttfc = turn.ttfc_ms || 500;
      await new Promise((r) => {
        playTimerRef.current = setTimeout(r, calculateDelay(ttfc, speed));
      });
      if (cancelled) return;
      setShowTyping(false);

      // Stream events
      const events = buildStreamEvents(turn);
      let lastTs = ttfc;

      for (let i = 0; i < events.length; i++) {
        if (cancelled) return;
        const evt = events[i];
        const gap = evt.ts - lastTs;
        if (gap > 0) {
          await new Promise((r) => {
            playTimerRef.current = setTimeout(r, calculateDelay(gap, speed));
          });
        }
        if (cancelled) return;
        lastTs = evt.ts;
        setStreamEvents((prev) => [...prev, evt]);
      }

      // Brief pause at end of turn
      await new Promise((r) => {
        playTimerRef.current = setTimeout(r, calculateDelay(300, speed));
      });
      if (cancelled) return;

      setStreaming(false);
      setStreamEvents([]);

      // Next turn
      if (turnIdx < N - 1) {
        playTurn(turnIdx + 1);
      } else {
        setPlaying(false);
      }
    };

    playTurn(idx);

    return () => {
      cancelled = true;
      if (playTimerRef.current) {
        clearTimeout(playTimerRef.current);
      }
    };
  }, [playing, N, turns, speed]);

  // Stop playback helper
  const stopPlayback = useCallback(() => {
    setPlaying(false);
    setStreaming(false);
    setShowTyping(false);
    setStreamEvents([]);
    if (playTimerRef.current) {
      clearTimeout(playTimerRef.current);
    }
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const fn = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
      if (e.key === 'ArrowRight' || e.key === 'l') {
        setIdx((p) => Math.min(p + 1, N - 1));
        stopPlayback();
      } else if (e.key === 'ArrowLeft' || e.key === 'h') {
        setIdx((p) => Math.max(p - 1, 0));
        stopPlayback();
      } else if (e.key === ' ') {
        e.preventDefault();
        if (playing) {
          stopPlayback();
        } else {
          setPlaying(true);
        }
      } else if (e.key >= '1' && e.key <= '6') {
        const tabs = ['rendered', 'output', 'diff', 'tree', 'prompt', 'cost'];
        setTab(tabs[+e.key - 1]);
      } else if (e.key === 'Home') {
        setIdx(0);
        stopPlayback();
      } else if (e.key === 'End') {
        setIdx(Math.max(0, N - 1));
        stopPlayback();
      } else if (e.key === 'Escape') {
        if (!data) navigate('/');
      }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, [N, data, navigate, playing, stopPlayback]);

  // Landing page when no data loaded
  if (!data) {
    return (
      <div className="fr-landing">
        <div className="fr-landing-header">
          <button className="fr-back-btn" onClick={() => navigate('/')}>
            &larr; Back
          </button>
          <span className="fr-landing-title">Flight Recorder</span>
        </div>

        <div className="fr-landing-content">
          <h2>Load Telemetry</h2>

          {/* Aide picker */}
          {aides.length > 0 && (
            <div className="fr-picker">
              <label>Select an aide</label>
              <select
                value={aideIdInput}
                onChange={(e) => {
                  setAideIdInput(e.target.value);
                  if (e.target.value) loadFromAPI(e.target.value);
                }}
              >
                <option value="">Choose aide...</option>
                {aides.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.title || 'Untitled'}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Manual ID input */}
          <div className="fr-manual-input">
            <label>Or enter Aide ID</label>
            <div className="fr-input-row">
              <input
                type="text"
                value={aideIdInput}
                onChange={(e) => setAideIdInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && loadFromAPI(aideIdInput)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />
              <button
                onClick={() => loadFromAPI(aideIdInput)}
                disabled={loading || !aideIdInput}
              >
                {loading ? 'Loading...' : 'Load'}
              </button>
            </div>
          </div>

          <div className="fr-divider">or</div>

          {/* File upload */}
          <button className="fr-upload-btn" onClick={() => fileRef.current?.click()}>
            Upload JSON File
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) loadFromFile(f);
            }}
            style={{ display: 'none' }}
          />

          {error && <div className="fr-error">{error}</div>}

          <div className="fr-hint">
            Supports eval golden format and telemetry API format
          </div>
        </div>
      </div>
    );
  }

  const isL4 = t.tier === 'L4';

  return (
    <div className="fr-container">
      {/* Top bar */}
      <div className="fr-topbar">
        <div className="fr-topbar-left">
          <button className="fr-back-btn" onClick={() => navigate('/')}>
            &larr;
          </button>
          <div className={`fr-status-dot ${playing ? 'fr-status-dot--playing' : ''}`} />
          <span className="fr-label">Flight Recorder</span>
          <span className="fr-name">{data.name}</span>
        </div>
        <div className="fr-topbar-right">
          <span className="fr-speed-label">Speed:</span>
          {[1, 2, 5, 0].map((s) => (
            <button
              key={s}
              className={`fr-speed-btn ${speed === s ? 'fr-speed-btn--active' : ''}`}
              onClick={() => setSpeed(s)}
            >
              {s === 0 ? '∞' : `${s}×`}
            </button>
          ))}
          <span className="fr-divider-v" />
          <span className="fr-turn-info">
            Turn {idx}/{N - 1}
          </span>
          {!isTurn0 && <TierBadge tier={t.tier} />}
          {!isTurn0 && (
            <span className="fr-timing">
              {t.ttfc_ms != null && `${t.ttfc_ms}ms ttft · `}
              {t.ttc_ms}ms ttc
            </span>
          )}
          {isTurn0 && <span className="fr-timing">Initial state</span>}
          <button
            className="fr-export-btn"
            onClick={async () => {
              try {
                const res = await fetch(`/api/aides/${data.aide_id}/telemetry/export`, { credentials: 'include' });
                if (!res.ok) {
                  // If API fails, export the local data directly
                  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `aide-telemetry-${data.aide_id || 'export'}.json`;
                  a.click();
                  URL.revokeObjectURL(url);
                  return;
                }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const contentDisposition = res.headers.get('content-disposition');
                const filenameMatch = contentDisposition?.match(/filename="(.+)"/);
                a.download = filenameMatch ? filenameMatch[1] : `aide-telemetry-${data.aide_id}.json`;
                a.click();
                URL.revokeObjectURL(url);
              } catch {
                // Fallback: export local data
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `aide-telemetry-${data.aide_id || 'export'}.json`;
                a.click();
                URL.revokeObjectURL(url);
              }
            }}
          >
            Export
          </button>
          <button className="fr-close-btn" onClick={() => setData(null)}>
            Close
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="fr-main">
        {/* Left: Chat */}
        <div className="fr-chat">
          <div className="fr-section-label">Conversation</div>
          {/* Turn 0: Initial state */}
          <div
            className={`fr-chat-turn fr-chat-turn--turn0 ${idx === 0 ? 'fr-chat-turn--active' : ''}`}
            onClick={() => {
              setIdx(0);
              setPlaying(false);
              setStreaming(false);
              setShowTyping(false);
            }}
          >
            <div className="fr-chat-bubble fr-chat-bubble--system">Initial state (empty)</div>
          </div>
          {/* Actual turns (1+) */}
          {turns.slice(0, actualTurnIdx + 1).map((tr, i) => (
            <div
              key={i}
              className={`fr-chat-turn ${i + 1 === idx ? 'fr-chat-turn--active' : ''}`}
              onClick={() => {
                setIdx(i + 1);
                setPlaying(false);
                setStreaming(false);
                setShowTyping(false);
              }}
            >
              {/* User message */}
              <div className="fr-chat-bubble">{tr.message}</div>
              {/* LLM response */}
              <div className="fr-chat-response">
                {/* Show streaming events for current turn during playback */}
                {i + 1 === idx && streaming && streamEvents.length > 0 && (
                  <div className="fr-mutations">
                    {streamEvents.map((evt, j) => {
                      if (evt.type === 'mutation') {
                        const tag = getMutationTag(evt.data);
                        if (!tag) return null;
                        return (
                          <div key={j} className="fr-mut-line">
                            <span className={`fr-mut-tag fr-mut-tag--${tag.type}`}>
                              {tag.label}
                            </span>
                            <span className="fr-mut-id">
                              {tag.id || ''}
                              {tag.from && tag.to && (
                                <>
                                  {tag.from}
                                  <span className="fr-mut-arrow">→</span>
                                  {tag.to}
                                </>
                              )}
                            </span>
                          </div>
                        );
                      }
                      if (evt.type === 'voice') {
                        return (
                          <div key={j} className="fr-voice-bubble">
                            {evt.text}
                          </div>
                        );
                      }
                      return null;
                    })}
                  </div>
                )}
                {/* Show completed response for all turns up to current (except current while streaming) */}
                {i + 1 <= idx && !(i + 1 === idx && streaming) && (
                  <>
                    {/* Voice/text responses - from text_blocks OR voice tool calls */}
                    {(() => {
                      const textBlockVoices = (tr.text_blocks || []).map((tb) =>
                        typeof tb === 'string' ? tb : tb.text
                      );
                      const toolCallVoices = parseToolCalls(tr.tool_calls)
                        .filter((tc) => tc.t === 'voice')
                        .map((tc) => tc.text);
                      const allVoices = [...textBlockVoices, ...toolCallVoices];
                      return allVoices.length > 0 ? (
                        <div className="fr-voice-responses">
                          {allVoices.map((text, j) => (
                            <div key={j} className="fr-voice-bubble">
                              {text}
                            </div>
                          ))}
                        </div>
                      ) : null;
                    })()}
                    {/* All tool calls (excluding voice) */}
                    {parseToolCalls(tr.tool_calls).filter((tc) => tc.t !== 'voice').length > 0 && (
                      <div className="fr-mutations">
                        {parseToolCalls(tr.tool_calls)
                          .filter((tc) => tc.t !== 'voice')
                          .map((tc, j) => {
                            const tag = getMutationTag(tc);
                            if (!tag) return null;
                            return (
                              <div key={j} className="fr-mut-line">
                                <span className={`fr-mut-tag fr-mut-tag--${tag.type}`}>
                                  {tag.label}
                                </span>
                                <span className="fr-mut-id">{tag.id || ''}</span>
                              </div>
                            );
                          })}
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className="fr-chat-meta">
                <TierBadge tier={tr.tier} small />
                <span className="fr-chat-timing">{tr.ttc_ms}ms</span>
              </div>
            </div>
          ))}
          {/* Typing indicator */}
          {showTyping && (
            <div className="fr-typing">
              <div className="fr-typing-dot" />
              <div className="fr-typing-dot" />
              <div className="fr-typing-dot" />
            </div>
          )}
        </div>

        {/* Center: Tabs + Content */}
        <div className="fr-center">
          <div className="fr-tabs">
            {[
              ['rendered', 'Rendered'],
              ['output', 'Raw Output'],
              ['diff', 'Before/After'],
              ['tree', 'Entity Tree'],
              ['prompt', 'Prompt'],
              ['cost', 'Cost'],
            ].map(([k, label], i) => (
              <button
                key={k}
                className={`fr-tab ${tab === k ? 'fr-tab--active' : ''}`}
                onClick={() => setTab(k)}
              >
                {i + 1}. {label}
              </button>
            ))}
          </div>

          <div className={`fr-content ${tab === 'rendered' ? 'fr-content--preview' : ''}`}>
            {/* 1. Rendered */}
            {tab === 'rendered' && <div ref={previewRef} className="fr-preview" />}

            {/* 2. Raw Output */}
            {tab === 'output' && (
              <div className="fr-output">
                {!isL4 && events.length > 0 && (
                  <div className="fr-events">
                    {events.map((e, i) => (
                      <EventPill key={i} event={e} />
                    ))}
                  </div>
                )}
                <div className="fr-section-label">Tool Calls</div>
                <pre className="fr-pre">{JSON.stringify(t.tool_calls, null, 2)}</pre>
                {t.text_blocks?.length > 0 && (
                  <>
                    <div className="fr-section-label" style={{ marginTop: 16 }}>
                      Text Blocks
                    </div>
                    <pre className="fr-pre">
                      {t.text_blocks
                        .map((b) => (typeof b === 'string' ? b : JSON.stringify(b)))
                        .join('\n\n')}
                    </pre>
                  </>
                )}
              </div>
            )}

            {/* 3. Before/After */}
            {tab === 'diff' && (
              <div className="fr-diff">
                <div className="fr-diff-grid">
                  <div>
                    <div className="fr-section-label">Before</div>
                    <pre className="fr-pre fr-pre--short">
                      {JSON.stringify(snapshotBefore, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <div className="fr-section-label">After</div>
                    <pre className="fr-pre fr-pre--short">
                      {JSON.stringify(snapshotAfter, null, 2)}
                    </pre>
                  </div>
                </div>
                <div className="fr-section-label">Entity Diff</div>
                <div className="fr-diff-pills">
                  {diff.add.map((k) => (
                    <span key={k} className="fr-diff-pill fr-diff-pill--add">
                      + {k}
                    </span>
                  ))}
                  {diff.mod
                    .filter((k) => !diff.moved[k])
                    .map((k) => (
                      <span
                        key={k}
                        className="fr-diff-pill fr-diff-pill--mod"
                        title={(diff.modDetails[k] || []).join(', ')}
                      >
                        ~ {k}
                      </span>
                    ))}
                  {Object.keys(diff.moved).map((k) => (
                    <span
                      key={k}
                      className="fr-diff-pill fr-diff-pill--moved"
                      title={`${diff.moved[k].from} -> ${diff.moved[k].to}`}
                    >
                      &rarr; {k}
                    </span>
                  ))}
                  {diff.rem.map((k) => (
                    <span key={k} className="fr-diff-pill fr-diff-pill--rem">
                      - {k}
                    </span>
                  ))}
                  {diff.add.length === 0 &&
                    diff.rem.length === 0 &&
                    diff.mod.length === 0 && (
                      <span className="fr-no-changes">No entity changes</span>
                    )}
                </div>
              </div>
            )}

            {/* 4. Entity Tree */}
            {tab === 'tree' && (
              <div className="fr-tree">
                <div className="fr-section-label">Entity Tree - Turn {t.turn}</div>
                {tree.length > 0 ? (
                  <div className="fr-tree-container">
                    {tree.map((e, i) => {
                      const nw = diff.add.includes(e.id);
                      const md = diff.mod.includes(e.id);
                      const rm = !!e._removed;
                      const mv = !!diff.moved[e.id];
                      const orph = !!e._orphan;
                      return (
                        <div
                          key={i}
                          className={`fr-tree-node ${rm ? 'fr-tree-node--removed' : ''}`}
                          style={{ paddingLeft: e.depth * 20 }}
                        >
                          <span className="fr-tree-prefix">
                            {e.depth > 0 ? '├─' : '◆'}
                          </span>
                          <span
                            className={`fr-tree-id ${nw ? 'fr-tree-id--new' : ''} ${md ? 'fr-tree-id--mod' : ''} ${rm ? 'fr-tree-id--rem' : ''} ${orph ? 'fr-tree-id--orphan' : ''}`}
                          >
                            {e.id}
                          </span>
                          {rm && <span className="fr-tree-tag fr-tree-tag--del">del</span>}
                          {orph && (
                            <span className="fr-tree-tag fr-tree-tag--orphan">orphan</span>
                          )}
                          {nw && <span className="fr-tree-tag fr-tree-tag--new">new</span>}
                          {mv && (
                            <span className="fr-tree-tag fr-tree-tag--moved">moved</span>
                          )}
                          {md && !mv && !orph && (
                            <span className="fr-tree-tag fr-tree-tag--mod">mod</span>
                          )}
                          {e.display && <span className="fr-tree-display">{e.display}</span>}
                          {e.props && Object.keys(e.props).length > 0 && (
                            <div className="fr-tree-props">
                              {Object.entries(e.props)
                                .slice(0, 5)
                                .map(([k, v]) => (
                                  <span key={k}>
                                    {k}={JSON.stringify(v).slice(0, 24)}
                                  </span>
                                ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="fr-empty">
                    No entities. {isL4 ? 'L4 turns are read-only queries.' : ''}
                  </div>
                )}
              </div>
            )}

            {/* 5. Prompt */}
            {tab === 'prompt' && (
              <div className="fr-prompt">
                <div className="fr-section-label">System Prompt</div>
                <pre className="fr-pre">{t.system_prompt || '(empty)'}</pre>
              </div>
            )}

            {/* 6. Cost */}
            {tab === 'cost' && (
              <div className="fr-cost">
                <div className="fr-cost-grid">
                  <div className="fr-cost-card">
                    <div className="fr-section-label">This Turn</div>
                    <div className="fr-cost-value fr-cost-value--turn">
                      ${turnCost.toFixed(6)}
                    </div>
                    <div className="fr-cost-sub">{t.tier} pricing</div>
                  </div>
                  <div className="fr-cost-card">
                    <div className="fr-section-label">Cumulative</div>
                    <div className="fr-cost-value fr-cost-value--cumulative">
                      ${cumulativeCost.toFixed(6)}
                    </div>
                    <div className="fr-cost-sub">Turns 0-{idx}</div>
                  </div>
                </div>

                <div className="fr-section-label" style={{ marginTop: 24 }}>
                  Token Breakdown
                </div>
                <table className="fr-cost-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Tokens</th>
                      <th>Rate</th>
                      <th>Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[
                      ['Input', t.usage?.input_tokens, COST_RATES[t.tier]?.in || 3],
                      ['Output', t.usage?.output_tokens, COST_RATES[t.tier]?.out || 15],
                      [
                        'Cache Read',
                        t.usage?.cache_read,
                        COST_RATES[t.tier]?.cache_read || 0.3,
                      ],
                      [
                        'Cache Write',
                        t.usage?.cache_creation,
                        COST_RATES[t.tier]?.cache_write || 3.75,
                      ],
                    ].map(([label, tokens, rate]) => (
                      <tr key={label}>
                        <td>{label}</td>
                        <td>{tokens || 0}</td>
                        <td>${rate}/1M</td>
                        <td>${(((tokens || 0) * rate) / 1e6).toFixed(6)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="fr-section-label" style={{ marginTop: 24 }}>
                  Cost by Turn
                </div>
                <div className="fr-cost-chart">
                  {turns.map((tr, i) => {
                    const cost = calculateCost(tr.usage, tr.model || tr.tier);
                    const maxCost = Math.max(
                      ...turns.map((x) => calculateCost(x.usage, x.model || x.tier))
                    );
                    const h = maxCost > 0 ? (cost / maxCost) * 80 : 0;
                    const c = TC[tr.tier] || TC.L3;
                    const turnIdx = i + 1; // Account for turn 0
                    return (
                      <div
                        key={i}
                        className={`fr-cost-bar ${turnIdx === idx ? 'fr-cost-bar--active' : ''} ${turnIdx > idx ? 'fr-cost-bar--future' : ''}`}
                        style={{
                          height: h + 10,
                          background: turnIdx === idx ? c.tx : c.bg,
                        }}
                        onClick={() => {
                          setIdx(turnIdx);
                          setPlaying(false);
                        }}
                        title={`Turn ${turnIdx}: $${cost.toFixed(6)}`}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Metrics */}
        <div className="fr-metrics">
          <div className="fr-section-label">Routing</div>
          <div className="fr-metric-row">
            <TierBadge tier={t.tier} />
            <span className="fr-model">{t.model}</span>
          </div>
          {t.temperature != null && (
            <div className="fr-metric-row">
              <span>Temperature</span>
              <span className="fr-metric-value">{t.temperature}</span>
            </div>
          )}

          <div className="fr-section-label" style={{ marginTop: 14 }}>
            Latency
          </div>
          <div className="fr-metric-row">
            <span>TTFC</span>
            <span className="fr-metric-value fr-metric-value--ttfc">
              {t.ttfc_ms != null ? `${t.ttfc_ms}ms` : '-'}
            </span>
          </div>
          <div className="fr-metric-row">
            <span>TTC</span>
            <span className="fr-metric-value">{t.ttc_ms ? `${t.ttc_ms}ms` : '-'}</span>
          </div>

          <div className="fr-section-label" style={{ marginTop: 14 }}>
            Tokens
          </div>
          {[
            ['Input', t.usage?.input_tokens],
            ['Output', t.usage?.output_tokens],
            ['Cache R', t.usage?.cache_read, 'cache'],
            ['Cache W', t.usage?.cache_creation],
          ].map(([k, v, cls]) => (
            <div key={k} className="fr-metric-row">
              <span>{k}</span>
              <span className={`fr-metric-value ${cls && v > 0 ? 'fr-metric-value--cache' : ''}`}>
                {v != null ? v : '-'}
              </span>
            </div>
          ))}

          <div className="fr-section-label" style={{ marginTop: 14 }}>
            Cost
          </div>
          <div className="fr-metric-row">
            <span>This turn</span>
            <span className="fr-metric-value fr-metric-value--cost-turn">
              ${turnCost.toFixed(4)}
            </span>
          </div>
          <div className="fr-metric-row">
            <span>Cumulative</span>
            <span className="fr-metric-value fr-metric-value--cost-cumulative">
              ${cumulativeCost.toFixed(4)}
            </span>
          </div>

          <div className="fr-section-label" style={{ marginTop: 14 }}>
            Tool Calls
          </div>
          <div className="fr-metric-value">{events.length} events</div>
          {events.length > 0 && (
            <div className="fr-event-summary">
              {Object.entries(
                events.reduce((acc, e) => {
                  acc[e.t] = (acc[e.t] || 0) + 1;
                  return acc;
                }, {})
              ).map(([type, count]) => (
                <div key={type}>
                  {type}: {count}
                </div>
              ))}
            </div>
          )}

          {t.validation && (
            <>
              <div className="fr-section-label" style={{ marginTop: 14 }}>
                Validation
              </div>
              <div
                className={`fr-validation ${t.validation.passed ? 'fr-validation--pass' : 'fr-validation--fail'}`}
              >
                {t.validation.passed ? 'PASSED' : 'FAILED'}
              </div>
              {t.validation.issues?.length > 0 && (
                <div className="fr-validation-issues">
                  {t.validation.issues.map((issue, i) => (
                    <div key={i}>{issue}</div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Timeline */}
      <div className="fr-timeline">
        <button
          className="fr-timeline-btn"
          onClick={() => {
            setIdx(0);
            setPlaying(false);
          }}
        >
          |&lt;
        </button>
        <button
          className="fr-timeline-btn"
          onClick={() => {
            setIdx((p) => Math.max(p - 1, 0));
            setPlaying(false);
          }}
        >
          &lt;
        </button>
        <button
          className={`fr-timeline-play ${playing ? 'fr-timeline-play--active' : ''}`}
          onClick={() => setPlaying((p) => !p)}
        >
          {playing ? '||' : '>'}
        </button>
        <button
          className="fr-timeline-btn"
          onClick={() => {
            setIdx((p) => Math.min(p + 1, N - 1));
            setPlaying(false);
          }}
        >
          &gt;
        </button>
        <button
          className="fr-timeline-btn"
          onClick={() => {
            setIdx(N - 1);
            setPlaying(false);
          }}
        >
          &gt;|
        </button>

        <div
          className="fr-timeline-track"
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            const p = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
            setIdx(Math.round(p * (N - 1)));
            setPlaying(false);
          }}
        >
          <div className="fr-timeline-bg" />
          <div
            className="fr-timeline-progress"
            style={{ width: `${(idx / Math.max(N - 1, 1)) * 100}%` }}
          />
          {/* Turn 0 marker */}
          <div
            className="fr-timeline-marker"
            style={{ left: '0%' }}
          >
            <div
              className={`fr-timeline-dot ${idx === 0 ? 'fr-timeline-dot--active' : ''}`}
              style={{
                background: idx === 0 ? '#94a3b8' : '#475569',
                borderColor: '#334155',
              }}
            />
          </div>
          {/* Actual turn markers */}
          {turns.map((tr, i) => {
            const c = TC[tr.tier] || TC.L3;
            const turnIdx = i + 1; // Account for turn 0
            const active = turnIdx === idx;
            return (
              <div
                key={i}
                className="fr-timeline-marker"
                style={{ left: `${(turnIdx / Math.max(N - 1, 1)) * 100}%` }}
              >
                <div
                  className={`fr-timeline-dot ${active ? 'fr-timeline-dot--active' : ''}`}
                  style={{
                    background: active ? c.tx : c.bg,
                    borderColor: c.bd,
                  }}
                />
              </div>
            );
          })}
        </div>

        <span className="fr-timeline-hint">&larr;&rarr; spc 1-6</span>
      </div>
    </div>
  );
}
