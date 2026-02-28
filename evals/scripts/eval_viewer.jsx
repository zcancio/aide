import { useState, useRef, useEffect, useCallback, useMemo } from "react";

// ── Model/tier constants ────────────────────────────────────────────────────

const MODELS = {
  L4: "claude-opus-4-5-20251101",
  L3: "claude-sonnet-4-5-20250929",
};
const TEMPS = { L4: 0, L3: 0 };

// ── Helpers ──────────────────────────────────────────────────────────────────

const hum = (s) => (s ? s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) : "");
const esc = (s) => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const tbText = (tb) => typeof tb === "string" ? tb : (tb?.text || "");
const tierBase = (t) => (t || "").split("->").pop();

function tierStyle(t) {
  const b = tierBase(t);
  return b === "L4" ? { bg: "#312e81", color: "#c4b5fd" } : { bg: "#0c3547", color: "#7dd3fc" };
}
function actionCls(a) {
  return ["create","update","remove","move","set"].includes(a) ? a : "unknown";
}

// ── Snapshot builder ────────────────────────────────────────────────────────

function buildSnap(g, ti) {
  const s = { entities: {}, rels: [], meta: {} };
  for (let i = 0; i <= ti; i++) {
    const t = g.turns[i];
    if (!t) break;
    for (const tc of t.tool_calls) {
      if (tc.name === "mutate_entity") {
        const p = tc.input;
        if (p.action === "create") s.entities[p.id] = { id: p.id, parent: p.parent || "root", display: p.display || null, props: { ...(p.props || {}) }, _removed: false };
        else if (p.action === "update" && s.entities[p.ref]) { Object.assign(s.entities[p.ref].props, p.props || {}); if (p.display) s.entities[p.ref].display = p.display; }
        else if (p.action === "remove" && s.entities[p.ref]) s.entities[p.ref]._removed = true;
        else if (p.action === "move" && s.entities[p.ref]) s.entities[p.ref].parent = p.parent;
      } else if (tc.name === "set_relationship") {
        const r = tc.input;
        if (r.action === "set") {
          if (r.cardinality === "one_to_one") s.rels = s.rels.filter(x => !(x.from === r.from && x.type === r.type));
          s.rels.push({ from: r.from, to: r.to, type: r.type, cardinality: r.cardinality || "many_to_one" });
        } else if (r.action === "remove") {
          s.rels = s.rels.filter(x => !(x.from === r.from && x.to === r.to && x.type === r.type));
        }
      }
    }
  }
  const pg = Object.values(s.entities).find((e) => e.parent === "root" && e.display === "page");
  if (pg) s.meta.title = pg.props.title || g.name;
  return s;
}

// ── Diff computation ────────────────────────────────────────────────────────

function computeDiff(g, ti) {
  const before = ti > 0 ? buildSnap(g, ti - 1) : { entities: {} };
  const after = buildSnap(g, ti);
  const added = [], updated = [], removed = [];

  for (const [id, e] of Object.entries(after.entities)) {
    if (!before.entities[id]) added.push(e);
    else if (e._removed && !before.entities[id]._removed) removed.push(e);
    else if (JSON.stringify(e.props) !== JSON.stringify(before.entities[id].props) || e.display !== before.entities[id].display) {
      updated.push({ id, before: before.entities[id], after: e });
    }
  }
  for (const id of Object.keys(before.entities)) {
    if (!after.entities[id]) removed.push(before.entities[id]);
  }
  return { before, after, added, updated, removed };
}

// ── Render snapshot → HTML string for iframe ────────────────────────────────

function renderHTML(s) {
  const E = s.entities;
  const rels = s.rels || [];
  const ch = (pid) => Object.values(E).filter((e) => e.parent === pid && !e._removed).sort((a, b) => (a.id > b.id ? 1 : -1));

  // Build rel lookups
  const inRels = {}, outRels = {};
  rels.forEach(r => {
    if (!inRels[r.to]) inRels[r.to] = [];
    inRels[r.to].push(r);
    if (!outRels[r.from]) outRels[r.from] = [];
    outRels[r.from].push(r);
  });
  const relTags = (eid) => {
    const all = [...(inRels[eid]||[]).map(r=>({dir:"in",r})), ...(outRels[eid]||[]).map(r=>({dir:"out",r}))];
    if (!all.length) return "";
    return all.map(({dir,r})=>{
      const other = dir==="in"?r.from:r.to;
      const nm = E[other]?.props?.name||E[other]?.props?.title||hum(other);
      const c = r.type==="absent"?"#dc2626":r.type==="sub"?"#f59e0b":r.type==="selected"?"#22c55e":"#6366f1";
      return `<span style="display:inline-block;font-size:10px;padding:1px 6px;border-radius:3px;background:${c}18;color:${c};border:1px solid ${c}40;margin-left:4px">${esc(r.type)}${dir==="in"?" ← ":" → "}${esc(nm)}</span>`;
    }).join("");
  };

  function tbl(sec) {
    const c = ch(sec.id);
    if (!c.length) return `<p class="em">Empty.</p>`;
    const ks = [...new Set(c.flatMap((x) => Object.keys(x.props).filter((k) => !k.startsWith("_"))))];
    const hasRels = c.some(x => inRels[x.id] || outRels[x.id]);
    return `<table><thead><tr>${ks.map((k) => `<th>${esc(hum(k))}</th>`).join("")}${hasRels?`<th></th>`:""}</tr></thead><tbody>${c.map((x) => `<tr>${ks.map((k) => { const v = x.props[k]; return `<td>${esc(v === true ? "✓" : v === false ? "✗" : String(v ?? "—"))}</td>`; }).join("")}${hasRels?`<td>${relTags(x.id)}</td>`:""}</tr>`).join("")}</tbody></table>`;
  }

  function gridH(sec) {
    const rows = sec.props._rows || 8, cols = sec.props._cols || 8, c = ch(sec.id), map = {};
    c.forEach((x) => { if (x.props.row !== undefined && x.props.col !== undefined) map[x.props.row + "_" + x.props.col] = x; });
    let h = `<div style="display:grid;grid-template-columns:repeat(${cols},1fr);gap:1px;background:#bbb;padding:1px;border-radius:4px;overflow:hidden">`;
    for (let r = 0; r < rows; r++) for (let c2 = 0; c2 < cols; c2++) { const cell = map[r + "_" + c2]; h += `<div style="background:${(r + c2) % 2 === 0 ? "#f0d9b5" : "#b58863"};min-height:26px;display:flex;align-items:center;justify-content:center;font-size:10px">${esc(cell?.props.piece || cell?.props.owner || "")}</div>`; }
    return h + "</div>";
  }

  function rend(e) {
    const c2 = ch(e.id), d = e.display || "card", nm = e.props.title || e.props.name || hum(e.id);
    const h2 = `<h2>${esc(nm)}</h2>`;
    if (d === "page") return `<h1>${esc(nm)}</h1>` + c2.map(rend).join("");
    if (d === "table") return `<div class="sec">${h2}${tbl(e)}</div>`;
    if (d === "section" || d === "list") return `<div class="sec">${h2}${c2.map(rend).join("") || '<p class="em">Empty.</p>'}</div>`;
    if (d === "checklist") return `<div class="sec">${h2}${ch(e.id).map((x) => { const done = x.props.done || x.props.checked || false; return `<div class="${done ? "ck done" : "ck"}">${done ? "☑" : "☐"} ${esc(x.props.name || hum(x.id))}</div>`; }).join("") || '<p class="em">Empty.</p>'}</div>`;
    if (d === "grid") return `<div class="sec">${h2}${gridH(e)}</div>`;
    if (d === "metric") return `<div class="met"><div class="mv">${esc(String(e.props.value || e.props.count || "—"))}</div><div class="ml">${esc(nm)}</div></div>`;
    if (d === "text") return `<p class="txt">${esc(e.props.content || e.props.text || "")}</p>`;
    return `<div class="card"><b>${esc(nm)}</b>${relTags(e.id)}<br/><span class="ps">${Object.entries(e.props).filter(([k]) => !k.startsWith("_") && k !== "title" && k !== "name").map(([k, v]) => `${esc(hum(k))}: ${esc(String(v ?? "—"))}`).join(" · ")}</span>${c2.map(rend).join("")}</div>`;
  }

  return `<!DOCTYPE html><html><head><link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=DM+Sans:wght@400;500&display=swap" rel="stylesheet"><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:'DM Sans',system-ui,sans-serif;background:#F7F5F2;color:#2D2D2A;padding:28px 36px}h1{font-family:'Playfair Display',serif;font-size:26px;font-weight:600;margin-bottom:24px}h2{font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:1.5px;color:#6B6963;margin-bottom:10px}.sec{margin-bottom:20px}table{width:100%;border-collapse:collapse}th{text-align:left;padding:5px 10px;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#8B8680;border-bottom:2px solid #E0DDD8;font-weight:500}td{padding:7px 10px;border-bottom:1px solid #E8E5E0;font-size:13px}.card{background:#fff;border:1px solid #E0DDD8;border-radius:6px;padding:12px;margin-bottom:8px}.ps{font-size:12px;color:#8B8680}.met{text-align:center;padding:16px}.mv{font-family:'Playfair Display',serif;font-size:32px;font-weight:700}.ml{font-size:11px;color:#8B8680;text-transform:uppercase;letter-spacing:1px;margin-top:3px}.txt{font-size:13px;line-height:1.6;color:#4A4A46;margin-bottom:16px}.ck{padding:3px 0;font-size:13px}.ck.done{text-decoration:line-through;opacity:.5}.em{color:#B5B0A8;font-style:italic;font-size:13px;padding:12px 0}</style></head><body>${ch("root").map(rend).join("")}</body></html>`;
}

// ── Styles ───────────────────────────────────────────────────────────────────

const S = {
  root: { height: "100vh", width: "100vw", display: "flex", flexDirection: "column", background: "#08080e", color: "#e2e8f0", fontFamily: "'DM Sans',system-ui,sans-serif", overflow: "hidden" },
  topbar: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 20px", borderBottom: "1px solid #1a1a2c", background: "#0c0c14", height: 40, flexShrink: 0 },
  main: { flex: 1, display: "flex", overflow: "hidden" },
  panelLeft: { width: 320, minWidth: 260, borderRight: "1px solid #1a1a2c", display: "flex", flexDirection: "column", background: "#0c0c14" },
  panelCenter: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 },
  panelRight: { width: 260, minWidth: 220, borderLeft: "1px solid #1a1a2c", display: "flex", flexDirection: "column", background: "#0c0c14", overflowY: "auto" },
  panelHeader: { padding: "6px 14px", fontSize: 9, fontWeight: 600, letterSpacing: "0.8px", textTransform: "uppercase", color: "#4e5468", borderBottom: "1px solid #1a1a2c", background: "#111119" },
  chatScroll: { flex: 1, overflowY: "auto", padding: "10px 12px" },
  viewTabs: { display: "flex", borderBottom: "1px solid #1a1a2c", background: "#0c0c14", flexShrink: 0 },
  viewContent: { flex: 1, overflow: "hidden", position: "relative" },
  timeline: { flexShrink: 0, background: "#0c0c14", borderTop: "1px solid #1a1a2c", padding: "8px 20px 12px" },
};

const vtabStyle = (active) => ({
  padding: "7px 16px", fontSize: 10, fontWeight: 500, letterSpacing: "0.3px",
  color: active ? "#3b82f6" : "#4e5468", cursor: "pointer",
  borderBottom: active ? "2px solid #3b82f6" : "2px solid transparent",
  userSelect: "none", transition: "0.15s",
});

const monoSm = { fontFamily: "'JetBrains Mono',monospace", fontSize: 10 };
const mrow = { display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 11 };
const msec = { padding: "12px 14px", borderBottom: "1px solid #1a1a2c" };
const mhdr = { fontSize: 9, fontWeight: 600, letterSpacing: "0.8px", textTransform: "uppercase", color: "#4e5468", marginBottom: 8 };

// ── Components ──────────────────────────────────────────────────────────────

function ToolPill({ tc }) {
  const a = tc.input?.action || "unknown";
  const id = tc.input?.id || tc.input?.ref || "";
  const cls = actionCls(a);
  const colors = {
    create: { bg: "#052e22", color: "#6ee7b7", border: "#065f46" },
    update: { bg: "#0c2d48", color: "#7dd3fc", border: "#0c4a6e" },
    remove: { bg: "#3b0f0f", color: "#fca5a5", border: "#7f1d1d" },
    move: { bg: "#2e1065", color: "#c4b5fd", border: "#4c1d95" },
    set: { bg: "#3d2800", color: "#fde68a", border: "#713f12" },
    unknown: { bg: "#1a1a28", color: "#94a3b8", border: "#252538" },
  };
  const c = colors[cls];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 3, padding: "1px 6px", borderRadius: 3, ...monoSm, fontSize: 9, background: c.bg, color: c.color, border: `1px solid ${c.border}`, whiteSpace: "nowrap" }}>
      <b>{a}</b>{id && <span style={{ opacity: 0.65 }}>{id}</span>}
    </span>
  );
}

function MetricsPanel({ golden, turnIdx }) {
  const t = golden.turns[turnIdx];
  const s = buildSnap(golden, turnIdx);
  const entCount = Object.values(s.entities).filter((e) => !e._removed).length;
  const tcSum = {};
  t.tool_calls.forEach((tc) => { const a = tc.input?.action || "?"; tcSum[a] = (tcSum[a] || 0) + 1; });

  let totalTools = 0, totalIn = 0, totalOut = 0;
  for (let i = 0; i <= turnIdx; i++) {
    totalTools += golden.turns[i].tool_calls.length;
    totalIn += golden.turns[i].usage?.input_tokens || 0;
    totalOut += golden.turns[i].usage?.output_tokens || 0;
  }

  const costIn = tierBase(t.tier) === "L4" ? (t.usage?.input_tokens || 0) * 15 / 1e6 : (t.usage?.input_tokens || 0) * 3 / 1e6;
  const costOut = tierBase(t.tier) === "L4" ? (t.usage?.output_tokens || 0) * 75 / 1e6 : (t.usage?.output_tokens || 0) * 15 / 1e6;

  const ts = tierStyle(t.tier);

  return (
    <>
      <div style={msec}>
        <div style={mhdr}>Routing</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Tier</span><span style={{ padding: "1px 8px", borderRadius: 3, fontWeight: 600, fontSize: 10, background: ts.bg, color: ts.color }}>{t.tier}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Model</span><span style={{ ...monoSm, color: "#4e5468", wordBreak: "break-all" }}>{MODELS[tierBase(t.tier)]}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Temperature</span><span style={{ ...monoSm, color: "#94a3b8" }}>{TEMPS[tierBase(t.tier)]}</span></div>
      </div>
      <div style={msec}>
        <div style={mhdr}>Latency</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>TTFC</span><span style={{ ...monoSm, color: t.ttfc_ms < 500 ? "#4ade80" : t.ttfc_ms < 1500 ? "#94a3b8" : "#fbbf24" }}>{t.ttfc_ms}ms</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>TTC</span><span style={{ ...monoSm, color: t.ttc_ms < 2000 ? "#4ade80" : t.ttc_ms < 5000 ? "#94a3b8" : "#fbbf24" }}>{t.ttc_ms}ms</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>ms/tool</span><span style={{ ...monoSm, color: "#94a3b8" }}>{t.tool_calls.length ? Math.round(t.ttc_ms / t.tool_calls.length) : "—"}</span></div>
      </div>
      <div style={msec}>
        <div style={mhdr}>Tokens</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Input</span><span style={monoSm}>{(t.usage?.input_tokens || 0).toLocaleString()}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Output</span><span style={monoSm}>{(t.usage?.output_tokens || 0).toLocaleString()}</span></div>
        {t.usage?.cache_read > 0 && <div style={mrow}><span style={{ color: "#4e5468" }}>Cache</span><span style={{ ...monoSm, color: "#4ade80" }}>{t.usage.cache_read.toLocaleString()} ({Math.round(t.usage.cache_read / t.usage.input_tokens * 100)}%)</span></div>}
        <div style={mrow}><span style={{ color: "#4e5468" }}>Est. cost</span><span style={{ ...monoSm, color: (costIn + costOut) < 0.01 ? "#4ade80" : "#94a3b8" }}>${(costIn + costOut).toFixed(4)}</span></div>
      </div>
      <div style={msec}>
        <div style={mhdr}>Tool Calls</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Total</span><span style={monoSm}>{t.tool_calls.length}</span></div>
        {Object.entries(tcSum).map(([a, c]) => <div key={a} style={mrow}><span style={{ color: "#4e5468" }}>{a}</span><span style={monoSm}>{c}</span></div>)}
        <div style={mrow}><span style={{ color: "#4e5468" }}>Text blocks</span><span style={monoSm}>{t.text_blocks?.length || 0}</span></div>
      </div>
      <div style={msec}>
        <div style={mhdr}>Snapshot</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Entities</span><span style={monoSm}>{entCount}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Relationships</span><span style={monoSm}>{s.rels.length}</span></div>
      </div>
      {t.validation && (
        <div style={msec}>
          <div style={mhdr}>Validation</div>
          {t.validation.passed ? <div style={{ color: "#4ade80", fontSize: 10 }}>✓ All checks passed</div> : t.validation.issues.map((iss, i) => <div key={i} style={{ color: "#fca5a5", fontSize: 10 }}>⚠ {iss}</div>)}
        </div>
      )}
      <div style={msec}>
        <div style={mhdr}>Cumulative (1–{turnIdx + 1})</div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Tools</span><span style={monoSm}>{totalTools}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Tokens in</span><span style={monoSm}>{totalIn.toLocaleString()}</span></div>
        <div style={mrow}><span style={{ color: "#4e5468" }}>Tokens out</span><span style={monoSm}>{totalOut.toLocaleString()}</span></div>
      </div>
    </>
  );
}

// ── Demo Data ────────────────────────────────────────────────────────────────

const DEMO_GOLDEN = {"scenario_id":"poker_league_demo","name":"Poker League","pattern":"roster + timeline + ledger","timestamp":"2026-02-26T15:00:00Z","turns":[{"turn":1,"tier":"L4","message":"I'm running a poker league. 8 players, Thursday nights biweekly, rotating hosts and snack duty. Players are Mike, Dave, Sarah, Linda, Tom, Amy, Jake, and Priya. Mike's hosting first game, Dave's on snacks.","tool_calls":[{"name":"mutate_entity","input":{"action":"create","id":"page","parent":"root","display":"page","props":{"title":"Poker League — Spring 2026"}}},{"name":"mutate_entity","input":{"action":"create","id":"roster","parent":"page","display":"table","props":{"title":"Roster","_pattern":"roster"}}},{"name":"mutate_entity","input":{"action":"create","id":"player_mike","parent":"roster","props":{"name":"Mike","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_dave","parent":"roster","props":{"name":"Dave","status":"active","snack_duty":true}}},{"name":"mutate_entity","input":{"action":"create","id":"player_sarah","parent":"roster","props":{"name":"Sarah","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_linda","parent":"roster","props":{"name":"Linda","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_tom","parent":"roster","props":{"name":"Tom","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_amy","parent":"roster","props":{"name":"Amy","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_jake","parent":"roster","props":{"name":"Jake","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"player_priya","parent":"roster","props":{"name":"Priya","status":"active","snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"schedule","parent":"page","display":"table","props":{"title":"Schedule","_pattern":"timeline"}}},{"name":"mutate_entity","input":{"action":"create","id":"game_1","parent":"schedule","props":{"date":"2026-02-19","host":"Mike","snacks":"Dave","status":"upcoming"}}}],"text_blocks":["Poker league. 8 players, biweekly Thursday.","Roster and schedule set. Mike hosting game 1, Dave on snacks."],"usage":{"input_tokens":1850,"output_tokens":680,"cache_read":0},"ttfc_ms":1320,"ttc_ms":4800,"validation":{"passed":true,"issues":[]}},{"turn":2,"tier":"L3","message":"We need to track standings too. Points, wins, and losses.","tool_calls":[{"name":"mutate_entity","input":{"action":"create","id":"standings","parent":"page","display":"table","props":{"title":"Standings","_pattern":"ledger","_sort_by":"points","_sort_order":"desc"}}}],"text_blocks":["Standings section added. Tracking points, wins, losses."],"usage":{"input_tokens":2400,"output_tokens":220,"cache_read":1600},"ttfc_ms":420,"ttc_ms":1200,"validation":{"passed":true,"issues":[]}},{"turn":3,"tier":"L3","message":"Mike's out this week. Dave's subbing in for hosting. Dave's on snacks since it was Mike's rotation.","tool_calls":[{"name":"mutate_entity","input":{"action":"update","ref":"player_mike","props":{"status":"out"}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_dave","props":{"snack_duty":true}}},{"name":"mutate_entity","input":{"action":"update","ref":"game_1","props":{"host":"Dave","snacks":"Dave"}}}],"text_blocks":["Mike out. Dave hosting and on snacks. 7 active."],"usage":{"input_tokens":2600,"output_tokens":190,"cache_read":1800},"ttfc_ms":350,"ttc_ms":980,"validation":{"passed":true,"issues":[]}},{"turn":4,"tier":"L3","message":"Game 1 results: Sarah won, Tom second, Linda third. Sarah 10 pts, Tom 7, Linda 5. Everyone else 2 points for showing up.","tool_calls":[{"name":"mutate_entity","input":{"action":"update","ref":"game_1","props":{"status":"complete","winner":"Sarah"}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_sarah","parent":"standings","props":{"name":"Sarah","points":10,"wins":1,"losses":0}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_tom","parent":"standings","props":{"name":"Tom","points":7,"wins":0,"losses":1}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_linda","parent":"standings","props":{"name":"Linda","points":5,"wins":0,"losses":1}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_dave","parent":"standings","props":{"name":"Dave","points":2,"wins":0,"losses":1}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_amy","parent":"standings","props":{"name":"Amy","points":2,"wins":0,"losses":1}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_jake","parent":"standings","props":{"name":"Jake","points":2,"wins":0,"losses":1}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_priya","parent":"standings","props":{"name":"Priya","points":2,"wins":0,"losses":1}}}],"text_blocks":["Game 1 recorded. Sarah leads with 10 points."],"usage":{"input_tokens":2900,"output_tokens":420,"cache_read":2000},"ttfc_ms":380,"ttc_ms":2100,"validation":{"passed":true,"issues":[]}},{"turn":5,"tier":"L3","message":"Actually let's also track a buy-in amount per player. Default $20.","tool_calls":[{"name":"mutate_entity","input":{"action":"update","ref":"player_mike","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_dave","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_sarah","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_linda","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_tom","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_amy","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_jake","props":{"buy_in":20}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_priya","props":{"buy_in":20}}}],"text_blocks":["Buy-in field added. $20 default across all 8 players."],"usage":{"input_tokens":3100,"output_tokens":340,"cache_read":2200},"ttfc_ms":360,"ttc_ms":1600,"validation":{"passed":true,"issues":[]}},{"turn":6,"tier":"L3","message":"Mike's back for game 2. Jake can't make it. Sarah's hosting, Priya on snacks.","tool_calls":[{"name":"mutate_entity","input":{"action":"update","ref":"player_mike","props":{"status":"active"}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_jake","props":{"status":"out"}}},{"name":"mutate_entity","input":{"action":"update","ref":"player_dave","props":{"snack_duty":false}}},{"name":"mutate_entity","input":{"action":"create","id":"game_2","parent":"schedule","props":{"date":"2026-03-05","host":"Sarah","snacks":"Priya","status":"upcoming"}}}],"text_blocks":["Mike active. Jake out for game 2. Sarah hosting, Priya on snacks."],"usage":{"input_tokens":3400,"output_tokens":250,"cache_read":2600},"ttfc_ms":330,"ttc_ms":1100,"validation":{"passed":true,"issues":[]}},{"turn":7,"tier":"L3","message":"Who's in the lead right now?","tool_calls":[],"text_blocks":["Sarah leads with 10 points and 1 win. Tom is second with 7, Linda third with 5. Dave, Amy, Jake, and Priya each have 2 points."],"usage":{"input_tokens":3600,"output_tokens":120,"cache_read":2800},"ttfc_ms":280,"ttc_ms":650,"validation":{"passed":true,"issues":[]}},{"turn":8,"tier":"L3","message":"Game 2 results: Mike won! Tom second again, Amy third. Mike 10, Tom 7, Amy 5, everyone else 2. Update the standings.","tool_calls":[{"name":"mutate_entity","input":{"action":"update","ref":"game_2","props":{"status":"complete","winner":"Mike"}}},{"name":"mutate_entity","input":{"action":"create","id":"standing_mike","parent":"standings","props":{"name":"Mike","points":10,"wins":1,"losses":0}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_tom","props":{"points":14,"losses":2}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_amy","props":{"points":7,"losses":2}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_sarah","props":{"points":12,"losses":1}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_linda","props":{"points":7,"losses":2}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_dave","props":{"points":4,"losses":2}}},{"name":"mutate_entity","input":{"action":"update","ref":"standing_priya","props":{"points":4,"losses":2}}}],"text_blocks":["Game 2 recorded. Tom leads overall at 14 points. Sarah 12, Mike 10."],"usage":{"input_tokens":3900,"output_tokens":380,"cache_read":3000},"ttfc_ms":340,"ttc_ms":1900,"validation":{"passed":true,"issues":[]}}]};

// ── Main App ────────────────────────────────────────────────────────────────

export default function EvalViewer() {
  const [golden, setGolden] = useState(DEMO_GOLDEN);
  const [cur, setCur] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [view, setView] = useState("rendered");
  const iframeRef = useRef(null);
  const chatEnd = useRef(null);
  const fileRef = useRef(null);

  const total = golden?.turns?.length || 0;
  const turn = golden?.turns?.[cur];
  const snapshot = useMemo(() => golden ? buildSnap(golden, cur) : null, [golden, cur]);
  const diff = useMemo(() => golden ? computeDiff(golden, cur) : null, [golden, cur]);

  // iframe update
  useEffect(() => { if (iframeRef.current && snapshot) iframeRef.current.srcdoc = renderHTML(snapshot); }, [snapshot]);

  // scroll chat
  useEffect(() => { chatEnd.current?.scrollIntoView({ behavior: "smooth" }); }, [cur]);

  // playback
  useEffect(() => {
    if (!playing) return;
    const iv = setInterval(() => { setCur((p) => { if (p >= total - 1) { setPlaying(false); return p; } return p + 1; }); }, 2500);
    return () => clearInterval(iv);
  }, [playing, total]);

  // keyboard
  useEffect(() => {
    const h = (e) => {
      if (e.key === "ArrowRight") { setCur((p) => Math.min(p + 1, total - 1)); setPlaying(false); }
      else if (e.key === "ArrowLeft") { setCur((p) => Math.max(p - 1, 0)); setPlaying(false); }
      else if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
      else if (e.key === "1") setView("rendered");
      else if (e.key === "2") setView("raw");
      else if (e.key === "3") setView("diff");
      else if (e.key === "4") setView("tree");
      else if (e.key === "5") setView("prompt");
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [total]);

  const goTo = useCallback((n) => { setCur(Math.max(0, Math.min(n, total - 1))); setPlaying(false); }, [total]);

  const handleFile = useCallback((e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = (ev) => { try { const d = JSON.parse(ev.target.result); if (d.turns?.length) { setGolden(d); setCur(0); setPlaying(false); } } catch {} };
    r.readAsText(f);
  }, []);

  const entCount = snapshot ? Object.values(snapshot.entities).filter((e) => !e._removed).length : 0;
  const progress = total > 1 ? (cur / (total - 1)) * 100 : 0;

  // Resizable panels
  const [leftW, setLeftW] = useState(320);
  const [rightW, setRightW] = useState(260);
  const dragRef = useRef(null);

  const startResize = useCallback((which, e) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = which === "left" ? leftW : rightW;
    dragRef.current = { which, startX, startW };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, [leftW, rightW]);

  useEffect(() => {
    const onMove = (e) => {
      if (!dragRef.current) return;
      const { which, startX, startW } = dragRef.current;
      const dx = e.clientX - startX;
      if (which === "left") setLeftW(Math.max(200, Math.min(600, startW + dx)));
      else setRightW(Math.max(180, Math.min(500, startW - dx)));
    };
    const onUp = () => {
      dragRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  const VIEWS = ["rendered", "raw", "diff", "tree", "prompt"];
  const VIEW_LABELS = { rendered: "Rendered", raw: "Raw Output", diff: "Before / After", tree: "Entity Tree", prompt: "Prompt" };

  return (
    <div style={S.root}>
      {/* Top bar */}
      <div style={S.topbar}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: playing ? "#ef4444" : "#4ade80", boxShadow: playing ? "0 0 8px #ef4444" : "0 0 6px rgba(74,222,128,.3)" }} />
          <span style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.7px", textTransform: "uppercase", color: "#4e5468" }}>Eval Viewer v3</span>
          <span style={{ fontSize: 12, color: "#94a3b8" }}>{golden?.name || "—"}</span>
          <span style={{ fontSize: 9, color: "#4e5468", background: "#111119", padding: "1px 6px", borderRadius: 3, border: "1px solid #1a1a2c" }}>{golden?.pattern || "—"}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 10, color: "#4e5468" }}>Turn {cur + 1}/{total || "—"} · {entCount} entities</span>
          <button onClick={() => fileRef.current?.click()} style={{ background: "#111119", border: "1px solid #252538", color: "#94a3b8", padding: "2px 10px", borderRadius: 4, cursor: "pointer", fontSize: 10, fontFamily: "inherit" }}>Load File</button>
          <input ref={fileRef} type="file" accept=".json" onChange={handleFile} style={{ display: "none" }} />
        </div>
      </div>

      {/* Main 3 panels */}
      <div style={S.main}>
        {/* LEFT: Chat */}
        <div style={{ ...S.panelLeft, width: leftW, minWidth: leftW }}>
          <div style={S.panelHeader}>Conversation</div>
          <div style={S.chatScroll}>
            {!golden && <p style={{ color: "#4e5468", padding: 16, fontSize: 12 }}>Load a golden file to begin.</p>}
            {golden?.turns.map((t, i) => (
              <div key={i} style={{ marginBottom: 12, opacity: i <= cur ? 1 : 0.12 }}>
                <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 4 }}>
                  <div style={{ maxWidth: "92%", padding: "7px 11px", fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", wordBreak: "break-word", background: "#12122a", color: "#b8c0d6", borderRadius: "11px 11px 2px 11px", border: "1px solid #1a1a2c" }}>{t.message}</div>
                </div>
                {t.text_blocks?.map((tb, j) => (
                  <div key={j} style={{ display: "flex", marginBottom: 4 }}>
                    <div style={{ maxWidth: "92%", padding: "7px 11px", fontSize: 12, lineHeight: 1.5, whiteSpace: "pre-wrap", background: "#fff", color: "#2D2D2A", borderRadius: "11px 11px 11px 2px", border: "1px solid #ddd" }}>{tbText(tb)}</div>
                  </div>
                ))}
                {!t.text_blocks?.length && t.tool_calls.length > 0 && i <= cur && (
                  <div style={{ fontSize: 10, color: "#4e5468", fontStyle: "italic", padding: "2px 8px" }}>[{t.tool_calls.length} mutations]</div>
                )}
              </div>
            ))}
            <div ref={chatEnd} />
          </div>
        </div>

        {/* Left resize handle */}
        <div onMouseDown={(e) => startResize("left", e)} style={{ width: 4, cursor: "col-resize", background: "transparent", flexShrink: 0, zIndex: 5 }} onMouseEnter={(e) => e.target.style.background = "#60a5fa"} onMouseLeave={(e) => { if (!dragRef.current) e.target.style.background = "transparent"; }} />

        {/* CENTER: 5 views */}
        <div style={S.panelCenter}>
          <div style={S.viewTabs}>
            {VIEWS.map((v) => (
              <div key={v} style={vtabStyle(view === v)} onClick={() => setView(v)}>{VIEW_LABELS[v]}</div>
            ))}
          </div>
          <div style={S.viewContent}>
            {view === "rendered" && (
              <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 12px", background: "#f8f8f6", borderBottom: "1px solid #E0DDD8", flexShrink: 0 }}>
                  <div style={{ display: "flex", gap: 4 }}><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#fecaca" }} /><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#fef3c7" }} /><span style={{ width: 8, height: 8, borderRadius: "50%", background: "#dcfce7" }} /></div>
                  <span style={{ fontSize: 10, color: "#999", fontFamily: "monospace" }}>toaide.com/s/{(golden?.scenario_id || "demo").replace(/_/g, "-")}</span>
                </div>
                <iframe ref={iframeRef} style={{ flex: 1, width: "100%", border: "none", background: "#F7F5F2" }} sandbox="allow-same-origin" title="Preview" />
              </div>
            )}
            {view === "raw" && turn && (
              <div style={{ padding: 16, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, lineHeight: 1.7, color: "#94a3b8", overflow: "auto", height: "100%" }}>
                {turn.text_blocks?.map((tb, i) => <div key={"t" + i} style={{ padding: "2px 0", borderBottom: "1px solid #1a1a2c" }}><span style={{ fontWeight: 600, color: "#22d3ee", marginRight: 6 }}>TEXT</span>{tbText(tb)}</div>)}
                {turn.tool_calls.map((tc, i) => <div key={i} style={{ padding: "2px 0", borderBottom: "1px solid #1a1a2c" }}><span style={{ fontWeight: 600, color: "#8b5cf6", marginRight: 6 }}>{tc.name}</span><span style={{ color: "#64748b" }}>{JSON.stringify(tc.input)}</span></div>)}
              </div>
            )}
            {view === "diff" && diff && (
              <div style={{ display: "flex", height: "100%" }}>
                <div style={{ flex: 1, overflow: "auto", padding: 16, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, lineHeight: 1.6, borderRight: "1px solid #1a1a2c" }}>
                  <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.6px", textTransform: "uppercase", color: "#4e5468", marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid #1a1a2c" }}>Before (Turn {cur})</div>
                  {diff.updated.map(({ id, before: b }) => (
                    <div key={id} style={{ marginBottom: 8, padding: "6px 8px", borderRadius: 4, border: "1px solid #0c4a6e", background: "rgba(59,130,246,.04)" }}>
                      <div style={{ fontWeight: 600, fontSize: 11 }}>{id}</div>
                      {Object.entries(b.props).filter(([k]) => !k.startsWith("_")).map(([k, v]) => JSON.stringify(v) !== JSON.stringify(diff.after.entities[id]?.props[k]) ? <div key={k} style={{ fontSize: 10, color: "#fca5a5", textDecoration: "line-through", marginTop: 2 }}>{k}: {String(v)}</div> : null)}
                    </div>
                  ))}
                </div>
                <div style={{ flex: 1, overflow: "auto", padding: 16, fontFamily: "'JetBrains Mono',monospace", fontSize: 11, lineHeight: 1.6 }}>
                  <div style={{ fontSize: 9, fontWeight: 600, letterSpacing: "0.6px", textTransform: "uppercase", color: "#4e5468", marginBottom: 10, paddingBottom: 6, borderBottom: "1px solid #1a1a2c" }}>After (Turn {cur + 1})</div>
                  {diff.added.map((e) => (
                    <div key={e.id} style={{ marginBottom: 8, padding: "6px 8px", borderRadius: 4, border: "1px solid #065f46", background: "rgba(74,222,128,.04)" }}>
                      <div style={{ fontWeight: 600, fontSize: 11 }}>+ {e.id}</div>
                      {Object.entries(e.props).filter(([k]) => !k.startsWith("_")).map(([k, v]) => <div key={k} style={{ fontSize: 10, color: "#6ee7b7", marginTop: 2 }}>{k}: {String(v)}</div>)}
                    </div>
                  ))}
                  {diff.updated.map(({ id, after: a }) => (
                    <div key={id} style={{ marginBottom: 8, padding: "6px 8px", borderRadius: 4, border: "1px solid #0c4a6e", background: "rgba(59,130,246,.04)" }}>
                      <div style={{ fontWeight: 600, fontSize: 11 }}>~ {id}</div>
                      {Object.entries(a.props).filter(([k]) => !k.startsWith("_")).map(([k, v]) => JSON.stringify(v) !== JSON.stringify(diff.before.entities[id]?.props[k]) ? <div key={k} style={{ fontSize: 10, color: "#6ee7b7", marginTop: 2 }}>{k}: {String(v)}</div> : null)}
                    </div>
                  ))}
                  {diff.removed.map((e) => (
                    <div key={e.id} style={{ marginBottom: 8, padding: "6px 8px", borderRadius: 4, border: "1px solid #7f1d1d", background: "rgba(252,165,165,.04)" }}>
                      <div style={{ fontWeight: 600, fontSize: 11, textDecoration: "line-through" }}>- {e.id}</div>
                    </div>
                  ))}
                  {!diff.added.length && !diff.updated.length && !diff.removed.length && <div style={{ color: "#4e5468", fontSize: 11 }}>No changes (query only).</div>}
                </div>
              </div>
            )}
            {view === "tree" && snapshot && (() => {
              const ch = (pid) => Object.values(snapshot.entities).filter((e) => e.parent === pid && !e._removed).sort((a, b) => (a.id > b.id ? 1 : -1));
              const addedIds = diff ? new Set(diff.added.map((e) => e.id)) : new Set();
              const updatedIds = diff ? new Set(diff.updated.map((c) => c.id)) : new Set();

              const Badge = ({ type, label }) => {
                const colors = { new: { bg: "#052e22", color: "#4ade80", border: "#166534" }, mod: { bg: "#0c2d48", color: "#60a5fa", border: "#1e40af" }, del: { bg: "#3b0f0f", color: "#f87171", border: "#991b1b" }, display: { bg: "#1e293b", color: "#94a3b8", border: "#334155" } };
                const c = colors[type] || colors.display;
                return <span style={{ display: "inline-block", fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3, marginLeft: 4, background: c.bg, color: c.color, border: `1px solid ${c.border}`, verticalAlign: "middle", lineHeight: 1.4 }}>{label}</span>;
              };

              const PropVal = ({ v }) => {
                if (v === null || v === undefined) return <span style={{ color: "#64748b" }}>null</span>;
                if (typeof v === "boolean") return <span style={{ color: "#c084fc" }}>{String(v)}</span>;
                if (typeof v === "number") return <span style={{ color: "#fbbf24" }}>{v}</span>;
                const s = String(v);
                return <span style={{ color: "#86efac" }}>"{s.length > 24 ? s.slice(0, 22) + "…" : s}"</span>;
              };

              function TreeNode({ e, prefix, isLast, isRoot }) {
                const kids = ch(e.id);
                const isNew = addedIds.has(e.id);
                const isUpd = updatedIds.has(e.id);
                const isDel = e._removed;
                const propEntries = Object.entries(e.props).filter(([k]) => !k.startsWith("_")).slice(0, 6);
                const childPrefix = isRoot ? "" : prefix + (isLast ? "    " : "│   ");

                return (
                  <>
                    <div style={{ padding: "1px 0", fontFamily: "'JetBrains Mono',monospace", fontSize: 11.5, lineHeight: 1.7, whiteSpace: "nowrap", ...(isDel ? { opacity: 0.3 } : {}) }}>
                      {isRoot
                        ? <span style={{ color: "#4ade80", marginRight: 4 }}>◆</span>
                        : <span style={{ color: "#444", whiteSpace: "pre" }}>{prefix}{isLast ? "└── " : "├── "}</span>
                      }
                      <span style={{ color: "#e2e8f0", fontWeight: 600, letterSpacing: "0.02em", ...(isDel ? { textDecoration: "line-through" } : {}) }}>{e.id}</span>
                      {isNew && <Badge type="new" label="new" />}
                      {isUpd && !isNew && <Badge type="mod" label="mod" />}
                      {isDel && <Badge type="del" label="del" />}
                      {e.display && <Badge type="display" label={e.display} />}
                      {e.props._pattern && <span style={{ display: "inline-block", fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3, marginLeft: 4, background: "#1e293b", color: "#a78bfa", border: "1px solid #6d28d9", verticalAlign: "middle", lineHeight: 1.4 }}>{e.props._pattern}</span>}
                      {propEntries.length > 0 && (
                        <>
                          <br />
                          <span style={{ color: "#444", whiteSpace: "pre" }}>{isRoot ? "  " : childPrefix.slice(0, -2) + "  "}</span>
                          <span style={{ color: "#64748b", fontSize: 10.5 }}>
                            {propEntries.map(([k, v], i) => (
                              <span key={k}>{i > 0 ? "  " : ""}<span style={{ color: "#94a3b8" }}>{k}</span>=<PropVal v={v} /></span>
                            ))}
                          </span>
                        </>
                      )}
                    </div>
                    {kids.map((k, i) => <TreeNode key={k.id} e={k} prefix={childPrefix} isLast={i === kids.length - 1} isRoot={false} />)}
                  </>
                );
              }

              const roots = ch("root");
              const prevRels = cur > 0 ? buildSnap(golden, cur - 1).rels : [];
              const prevRelKeys = new Set(prevRels.map(r => `${r.from}→${r.to}:${r.type}`));

              return (
                <div style={{ padding: 16, overflow: "auto", height: "100%", fontFamily: "'JetBrains Mono',monospace" }}>
                  <div style={{ color: "#64748b", marginBottom: 8, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Entity Tree — Turn {cur + 1}</div>
                  {roots.length === 0 ? <div style={{ color: "#4e5468", padding: 12 }}>No entities yet.</div> : roots.map((r, i) => <TreeNode key={r.id} e={r} prefix="" isLast={i === roots.length - 1} isRoot={true} />)}
                  {snapshot.rels.length > 0 && (
                    <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #1e293b" }}>
                      <div style={{ color: "#64748b", marginBottom: 6, fontSize: 10, textTransform: "uppercase", letterSpacing: "0.1em" }}>Relationships</div>
                      {snapshot.rels.map((r, i) => {
                        const key = `${r.from}→${r.to}:${r.type}`;
                        const isNewRel = !prevRelKeys.has(key);
                        return (
                          <div key={i} style={{ padding: "2px 0", fontSize: 11.5, lineHeight: 1.7, whiteSpace: "nowrap" }}>
                            <span style={{ color: "#94a3b8" }}>{r.from}</span>
                            <span style={{ color: "#fbbf24", margin: "0 6px" }}>─{r.type}→</span>
                            <span style={{ color: "#94a3b8" }}>{r.to}</span>
                            {r.cardinality && <span style={{ display: "inline-block", fontSize: 8, fontWeight: 600, padding: "1px 5px", borderRadius: 3, marginLeft: 4, background: "#1e293b", color: "#a78bfa", border: "1px solid #6d28d9", verticalAlign: "middle", lineHeight: 1.4 }}>{r.cardinality}</span>}
                            {isNewRel && <span style={{ display: "inline-block", fontSize: 9, fontWeight: 600, padding: "1px 5px", borderRadius: 3, marginLeft: 4, background: "#052e22", color: "#4ade80", border: "1px solid #166534", verticalAlign: "middle", lineHeight: 1.4 }}>new</span>}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
            {view === "prompt" && (
              <div style={{ padding: 16, overflow: "auto", height: "100%", fontFamily: "'JetBrains Mono',monospace", fontSize: 11, lineHeight: 1.65, color: "#94a3b8", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {turn?.system_prompt ? turn.system_prompt.split("\n").map((line, i) => {
                  if (line.startsWith("# ") || line.startsWith("## ") || line.startsWith("### ")) return <div key={i} style={{ color: "#60a5fa", fontWeight: 600, marginTop: 16 }}>{line}</div>;
                  if (line.includes("Current Snapshot") || line.startsWith("```")) return <div key={i} style={{ color: "#fbbf24", opacity: 0.7, fontSize: 10 }}>{line}</div>;
                  return <div key={i}>{line}</div>;
                }) : <div style={{ color: "#4e5468", fontStyle: "italic" }}>No prompt data. Re-run eval to capture prompts.</div>}
              </div>
            )}
        </div>

        {/* Right resize handle */}
        <div onMouseDown={(e) => startResize("right", e)} style={{ width: 4, cursor: "col-resize", background: "transparent", flexShrink: 0, zIndex: 5 }} onMouseEnter={(e) => e.target.style.background = "#60a5fa"} onMouseLeave={(e) => { if (!dragRef.current) e.target.style.background = "transparent"; }} />

        {/* RIGHT: Metrics */}
        <div style={{ ...S.panelRight, width: rightW, minWidth: rightW }}>
          <div style={S.panelHeader}>Turn Metrics</div>
          {golden && turn ? <MetricsPanel golden={golden} turnIdx={cur} /> : <div style={{ padding: 16, color: "#4e5468", fontSize: 12 }}>No data loaded.</div>}
        </div>
      </div>

      {/* Timeline */}
      <div style={S.timeline}>
        <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 6 }}>
          <button onClick={() => goTo(0)} style={{ background: "none", border: "none", color: "#4e5468", cursor: "pointer", fontSize: 13, padding: "2px 4px" }}>⏮</button>
          <button onClick={() => goTo(cur - 1)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13, padding: "2px 4px" }}>◂</button>
          <button onClick={() => setPlaying((p) => !p)} style={{ width: 28, height: 28, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, color: "#fff", border: "none", cursor: "pointer", background: playing ? "#ef4444" : "#3b82f6", boxShadow: playing ? "0 0 12px rgba(239,68,68,.3)" : "0 0 12px rgba(59,130,246,.3)" }}>{playing ? "⏸" : "▶"}</button>
          <button onClick={() => goTo(cur + 1)} style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: 13, padding: "2px 4px" }}>▸</button>
          <button onClick={() => goTo(total - 1)} style={{ background: "none", border: "none", color: "#4e5468", cursor: "pointer", fontSize: 13, padding: "2px 4px" }}>⏭</button>
          <span style={{ fontSize: 9, color: "#4e5468", marginLeft: 8 }}>←→ step · Space play · 1-4 views</span>
        </div>
        <div onClick={(e) => { if (!golden) return; const r = e.currentTarget.getBoundingClientRect(); goTo(Math.round(((e.clientX - r.left) / r.width) * (total - 1))); }} style={{ height: 5, background: "#111119", borderRadius: 3, cursor: "pointer", position: "relative" }}>
          <div style={{ height: "100%", width: `${progress}%`, borderRadius: 3, background: "linear-gradient(90deg,#3b82f6,#8b5cf6)", transition: "width 0.2s" }} />
          {golden?.turns.map((t, i) => {
            const pos = total > 1 ? (i / (total - 1)) * 100 : 0;
            const ts = tierStyle(t.tier);
            return <div key={i} onClick={(e) => { e.stopPropagation(); goTo(i); }} style={{ position: "absolute", left: `${pos}%`, top: -4, width: 12, height: 12, borderRadius: "50%", transform: "translateX(-50%)", cursor: "pointer", border: `2px solid ${i <= cur ? ts.bg : "#252538"}`, background: i <= cur ? ts.bg : "#111119", transition: "0.15s" }} title={`Turn ${i + 1} (${t.tier})`} />;
          })}
        </div>
      </div>
    </div>
  );
}
