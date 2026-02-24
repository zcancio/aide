#!/usr/bin/env node
/**
 * Node bridge for AIde CLI.
 * Loads engine.js, exposes renderText + reduce over stdin/stdout JSON-RPC.
 * Long-lived process — spawned once per CLI session.
 */

const path = require("path");
const os = require("os");
const readline = require("readline");

// Get engine path from args or use default
const enginePath = process.argv[2] || path.join(os.homedir(), ".aide", "engine.js");

let engine;
try {
  engine = require(enginePath);
} catch (err) {
  console.error(JSON.stringify({ error: `Failed to load engine: ${err.message}` }));
  process.exit(1);
}

// Extract available functions (not all may be present)
const { reduce, replay, emptyState, renderTextCli } = engine;

const rl = readline.createInterface({ input: process.stdin });

rl.on("line", (line) => {
  try {
    const req = JSON.parse(line);
    let result;

    switch (req.method) {
      case "renderText":
        if (!renderTextCli) {
          result = { error: "renderTextCli not available in engine" };
        } else {
          result = renderTextCli(req.params.snapshot);
        }
        break;

      case "reduce":
        if (!reduce) {
          result = { error: "reduce not available in engine" };
        } else {
          result = reduce(req.params.snapshot, req.params.event);
        }
        break;

      case "replay":
        if (!replay) {
          result = { error: "replay not available in engine" };
        } else {
          result = replay(req.params.events);
        }
        break;

      case "ping":
        result = "pong";
        break;

      default:
        result = { error: `Unknown method: ${req.method}` };
    }

    process.stdout.write(JSON.stringify({ id: req.id, result }) + "\n");
  } catch (err) {
    process.stdout.write(JSON.stringify({
      id: null,
      error: err.message
    }) + "\n");
  }
});

// Signal readiness
process.stdout.write(JSON.stringify({ ready: true }) + "\n");
