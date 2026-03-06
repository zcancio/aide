/**
 * Playground.jsx - Entity state validator and renderer
 *
 * Input panel for entity state JSON, validates syntax,
 * renders in preview panel using the same renderer as editor/flight recorder.
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import { renderHtml, RENDERER_CSS } from '../lib/display/index.js';

// Example entity state for placeholder
const EXAMPLE_STATE = {
  meta: { title: null },
  entities: {
    page: {
      id: 'page',
      parent: 'root',
      display: 'page',
      props: { title: 'My Page' },
      _removed: false,
      _children: ['section_1'],
      _created_seq: 1,
      _updated_seq: 1,
    },
    section_1: {
      id: 'section_1',
      parent: 'page',
      display: 'section',
      props: { title: 'Section One' },
      _removed: false,
      _children: ['item_1'],
      _created_seq: 2,
      _updated_seq: 2,
    },
    item_1: {
      id: 'item_1',
      parent: 'section_1',
      display: 'card',
      props: { title: 'Card Item', description: 'A sample card' },
      _removed: false,
      _children: [],
      _created_seq: 3,
      _updated_seq: 3,
    },
  },
  relationships: [],
  _sequence: 3,
};

export default function Playground() {
  const [input, setInput] = useState(JSON.stringify(EXAMPLE_STATE, null, 2));
  const [error, setError] = useState(null);
  const [copyFeedback, setCopyFeedback] = useState(null);
  const [darkMode, setDarkMode] = useState(false);
  const previewRef = useRef(null);
  const shadowRef = useRef(null);

  // Light mode: force light variables (override system dark mode preference)
  const lightThemeOverrides = `
    :host {
      --text-primary: #2D2D2A;
      --text-secondary: #6B6963;
      --text-tertiary: #A8A5A0;
      --bg-primary: #F7F5F2;
      --bg-secondary: #EFECEA;
      --bg-tertiary: #E6E3DF;
      --bg-elevated: #FFFFFF;
      --border-subtle: #E0DDD8;
      --border-default: #D4D1CC;
      --border-strong: #A8A5A0;
      --border: var(--border-default);
      --border-light: var(--border-subtle);
    }
  `;

  // Dark mode: override CSS custom properties to match dark scheme
  const darkThemeOverrides = `
    :host {
      --text-primary: #E6E3DF;
      --text-secondary: #A8A5A0;
      --text-tertiary: #6B6963;
      --bg-primary: #1A1A18;
      --bg-secondary: #242422;
      --bg-tertiary: #2D2D2A;
      --bg-elevated: #242422;
      --border-subtle: #2F2F2B;
      --border-default: #3A3A36;
      --border-strong: #4A4A44;
      --border: var(--border-default);
      --border-light: var(--border-subtle);
      --accent-hover: #8FA07E;
    }
  `;

  // Initialize Shadow DOM
  useEffect(() => {
    if (!previewRef.current) return;
    if (previewRef.current.shadowRoot) {
      shadowRef.current = previewRef.current.shadowRoot;
      return;
    }
    if (shadowRef.current) return;

    const shadow = previewRef.current.attachShadow({ mode: 'open' });
    shadowRef.current = shadow;

    const style = document.createElement('style');
    style.id = 'theme-style';
    style.textContent = RENDERER_CSS + (darkMode ? darkThemeOverrides : lightThemeOverrides);
    shadow.appendChild(style);

    const content = document.createElement('div');
    content.className = 'aide-preview-content';
    shadow.appendChild(content);
  }, []);

  // Update theme when darkMode changes
  useEffect(() => {
    if (!shadowRef.current) return;
    const style = shadowRef.current.getElementById('theme-style');
    if (style) {
      style.textContent = RENDERER_CSS + (darkMode ? darkThemeOverrides : lightThemeOverrides);
    }
  }, [darkMode]);

  // Parse and render when input changes
  useEffect(() => {
    if (!shadowRef.current) return;
    const content = shadowRef.current.querySelector('.aide-preview-content');
    if (!content) return;

    try {
      const parsed = JSON.parse(input);
      setError(null);

      // Convert to renderHtml format
      const entities = parsed.entities || {};
      const rootIds = Object.keys(entities).filter(
        (id) => !entities[id].parent || entities[id].parent === 'root'
      );
      const store = { entities, rootIds, meta: parsed.meta || {} };
      const html = renderHtml(store);
      content.innerHTML = html;
    } catch (e) {
      setError(e.message);
      content.innerHTML = `<div style="color: #dc2626; padding: 16px;">Invalid JSON: ${e.message}</div>`;
    }
  }, [input]);

  const copyEntityState = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(input);
      setCopyFeedback('state');
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  }, [input]);

  const copyRenderedHtml = useCallback(async () => {
    if (!shadowRef.current) return;
    const content = shadowRef.current.querySelector('.aide-preview-content');
    if (!content) return;

    try {
      await navigator.clipboard.writeText(content.innerHTML);
      setCopyFeedback('html');
      setTimeout(() => setCopyFeedback(null), 2000);
    } catch (e) {
      console.error('Failed to copy:', e);
    }
  }, []);

  const formatJson = useCallback(() => {
    try {
      const parsed = JSON.parse(input);
      setInput(JSON.stringify(parsed, null, 2));
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [input]);

  const clearInput = useCallback(() => {
    setInput('{\n  "meta": {},\n  "entities": {}\n}');
  }, []);

  return (
    <div className="pg-container">
      <header className="pg-header">
        <h1 className="pg-title">Entity State Playground</h1>
        <div className="pg-header-actions">
          <a href="/" className="pg-link">Dashboard</a>
          <a href="/flight-recorder" className="pg-link">Flight Recorder</a>
        </div>
      </header>

      <div className="pg-main">
        {/* Input Panel */}
        <div className="pg-panel pg-input-panel">
          <div className="pg-panel-header">
            <span className="pg-panel-title">Entity State JSON</span>
            <div className="pg-panel-actions">
              <button onClick={formatJson} className="pg-btn pg-btn--secondary">
                Format
              </button>
              <button onClick={clearInput} className="pg-btn pg-btn--secondary">
                Clear
              </button>
              <button onClick={copyEntityState} className="pg-btn pg-btn--primary">
                {copyFeedback === 'state' ? 'Copied!' : 'Copy JSON'}
              </button>
            </div>
          </div>
          <textarea
            className="pg-textarea"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            spellCheck={false}
            placeholder="Paste entity state JSON here..."
          />
          {error && (
            <div className="pg-error">
              <strong>Syntax Error:</strong> {error}
            </div>
          )}
        </div>

        {/* Preview Panel */}
        <div className="pg-panel pg-preview-panel">
          <div className="pg-panel-header">
            <span className="pg-panel-title">Rendered Preview</span>
            <div className="pg-panel-actions">
              <button
                onClick={() => setDarkMode(!darkMode)}
                className="pg-btn pg-btn--toggle"
                title={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
              >
                {darkMode ? 'Light' : 'Dark'}
              </button>
              <button onClick={copyRenderedHtml} className="pg-btn pg-btn--primary">
                {copyFeedback === 'html' ? 'Copied!' : 'Copy HTML'}
              </button>
            </div>
          </div>
          <div className={`pg-preview ${darkMode ? 'pg-preview--dark' : ''}`} ref={previewRef} />
        </div>
      </div>

      <style>{`
        .pg-container {
          display: flex;
          flex-direction: column;
          height: 100vh;
          background: #0f0f0f;
          color: #e8e6e3;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }

        .pg-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 12px 20px;
          background: #1a1a1a;
          border-bottom: 1px solid #333;
        }

        .pg-title {
          font-size: 18px;
          font-weight: 600;
          margin: 0;
        }

        .pg-header-actions {
          display: flex;
          gap: 16px;
        }

        .pg-link {
          color: #94a3b8;
          text-decoration: none;
          font-size: 14px;
        }

        .pg-link:hover {
          color: #e8e6e3;
        }

        .pg-main {
          display: flex;
          flex: 1;
          overflow: hidden;
        }

        .pg-panel {
          display: flex;
          flex-direction: column;
          flex: 1;
          min-width: 0;
        }

        .pg-input-panel {
          border-right: 1px solid #333;
        }

        .pg-panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 10px 16px;
          background: #1a1a1a;
          border-bottom: 1px solid #333;
        }

        .pg-panel-title {
          font-size: 14px;
          font-weight: 500;
          color: #94a3b8;
        }

        .pg-panel-actions {
          display: flex;
          gap: 8px;
        }

        .pg-btn {
          padding: 6px 12px;
          font-size: 13px;
          font-weight: 500;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.15s;
        }

        .pg-btn--primary {
          background: #2563eb;
          color: white;
        }

        .pg-btn--primary:hover {
          background: #1d4ed8;
        }

        .pg-btn--secondary {
          background: #333;
          color: #e8e6e3;
        }

        .pg-btn--secondary:hover {
          background: #444;
        }

        .pg-textarea {
          flex: 1;
          padding: 16px;
          background: #0f0f0f;
          color: #e8e6e3;
          border: none;
          font-family: 'SF Mono', Monaco, Consolas, monospace;
          font-size: 13px;
          line-height: 1.5;
          resize: none;
          outline: none;
        }

        .pg-textarea::placeholder {
          color: #555;
        }

        .pg-error {
          padding: 10px 16px;
          background: #450a0a;
          color: #fca5a5;
          font-size: 13px;
          border-top: 1px solid #7f1d1d;
        }

        .pg-preview {
          flex: 1;
          overflow: auto;
          background: #F7F5F2;
        }

        .pg-preview--dark {
          background: #1A1A18;
        }

        .pg-btn--toggle {
          background: #1e293b;
          color: #94a3b8;
          border: 1px solid #334155;
        }

        .pg-btn--toggle:hover {
          background: #334155;
          color: #e8e6e3;
        }
      `}</style>
    </div>
  );
}
