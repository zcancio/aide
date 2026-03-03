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
  const [entityStore] = useState(getDemoEntityTree);

  const handleDirectEdit = (entityId, field, value) => {
    // In a real app, this would update the entity store
    console.log('Direct edit:', { entityId, field, value });
  };

  return (
    <div className="demo-patterns-page">
      <div className="demo-preview-container">
        <Preview entityStore={entityStore} onDirectEdit={handleDirectEdit} />
      </div>

      <style>{`
        .demo-patterns-page {
          height: 100vh;
        }

        .demo-preview-container {
          height: 100%;
          overflow: auto;
        }

        .demo-preview-container .aide-preview {
          height: 100%;
          overflow-y: auto;
        }
      `}</style>
    </div>
  );
}
