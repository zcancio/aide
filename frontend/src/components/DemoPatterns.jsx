/**
 * DemoPatterns.jsx - Demo page for all pattern types and display variants
 *
 * This page displays a comprehensive mock entity tree for testing and
 * documenting all supported pattern types, display hints, and edge cases.
 */

import { useState } from 'react';
import Preview from './Preview.jsx';
import { getDemoEntityTree } from '../lib/display/demo-entity-tree.js';

export default function DemoPatterns() {
  const [entityStore] = useState(getDemoEntityTree());

  const handleDirectEdit = (entityId, field, value) => {
    // In a real app, this would update the entity store
    console.log('Direct edit:', { entityId, field, value });
  };

  return (
    <div className="demo-patterns-page">
      <div className="demo-header">
        <div className="demo-header-content">
          <h1>AIde Pattern Library</h1>
          <p>
            Comprehensive demonstration of all supported pattern types, display hints,
            and edge cases. Use this page to verify rendering behavior and as a visual
            reference for the display system.
          </p>
          <div className="demo-info">
            <span className="demo-badge">Read-only</span>
            <span className="demo-badge">All Patterns</span>
            <span className="demo-badge">{Object.keys(entityStore.entities).length} Entities</span>
          </div>
        </div>
      </div>

      <div className="demo-preview-container">
        <Preview entityStore={entityStore} onDirectEdit={handleDirectEdit} />
      </div>

      <style>{`
        .demo-patterns-page {
          height: 100vh;
          display: flex;
          flex-direction: column;
          background: #F7F5F2;
        }

        .demo-header {
          background: #FFFFFF;
          border-bottom: 1px solid #E0DDD8;
          padding: 24px 32px;
          flex-shrink: 0;
        }

        .demo-header-content {
          max-width: 720px;
          margin: 0 auto;
        }

        .demo-header h1 {
          font-family: 'Playfair Display', Georgia, serif;
          font-size: 32px;
          font-weight: 700;
          color: #2D2D2A;
          margin: 0 0 8px 0;
        }

        .demo-header p {
          font-family: 'DM Sans', -apple-system, sans-serif;
          font-size: 15px;
          line-height: 1.6;
          color: #6B6963;
          margin: 0 0 16px 0;
        }

        .demo-info {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
        }

        .demo-badge {
          display: inline-block;
          padding: 4px 12px;
          background: #F0F3ED;
          border: 1px solid #DDE4D7;
          border-radius: 16px;
          font-size: 12px;
          font-weight: 600;
          color: #667358;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }

        .demo-preview-container {
          flex: 1;
          overflow: auto;
          position: relative;
        }

        .demo-preview-container .aide-preview {
          height: 100%;
          overflow-y: auto;
        }

        @media (prefers-color-scheme: dark) {
          .demo-patterns-page {
            background: #1A1A18;
          }

          .demo-header {
            background: #242422;
            border-bottom-color: #2F2F2B;
          }

          .demo-header h1 {
            color: #E6E3DF;
          }

          .demo-header p {
            color: #A8A5A0;
          }

          .demo-badge {
            background: #2D2D2A;
            border-color: #3A3A36;
            color: #8FA07E;
          }
        }
      `}</style>
    </div>
  );
}
