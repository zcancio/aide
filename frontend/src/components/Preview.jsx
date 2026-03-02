/**
 * Preview.jsx - Preview component with Shadow DOM rendering
 */

import { useEffect, useRef, useLayoutEffect } from 'react';
import * as display from '../../display.js';

export default function Preview({ entityStore, onDirectEdit }) {
  const containerRef = useRef(null);
  const shadowRef = useRef(null);
  const scrollPosRef = useRef(0);

  // Initialize Shadow DOM once
  useEffect(() => {
    if (!containerRef.current || shadowRef.current) return;

    const shadow = containerRef.current.attachShadow({ mode: 'open' });
    shadowRef.current = shadow;

    // Add stylesheet to shadow DOM
    const style = document.createElement('style');
    style.textContent = display.RENDERER_CSS;
    shadow.appendChild(style);

    // Create content container
    const content = document.createElement('div');
    content.className = 'aide-preview-content';
    shadow.appendChild(content);
  }, []);

  // Render content
  useLayoutEffect(() => {
    if (!shadowRef.current) return;

    const content = shadowRef.current.querySelector('.aide-preview-content');
    if (!content) return;

    // Save scroll position
    const scrollContainer = containerRef.current;
    if (scrollContainer) {
      scrollPosRef.current = scrollContainer.scrollTop;
    }

    // Render HTML
    const html = display.renderHtml(entityStore);
    content.innerHTML = html;

    // Restore scroll position
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollPosRef.current;
    }

    // Event delegation for editable fields
    const handleClick = (e) => {
      const editable = e.target.closest('.editable-field');
      if (editable && onDirectEdit) {
        const entityId = editable.dataset.entityId;
        const field = editable.dataset.field;
        const currentValue = editable.textContent;

        const newValue = prompt(`Edit ${field}:`, currentValue);
        if (newValue !== null && newValue !== currentValue) {
          onDirectEdit(entityId, field, newValue);
        }
      }

      // Handle checkboxes
      const checkbox = e.target.closest('.aide-checklist__checkbox');
      if (checkbox && onDirectEdit) {
        const entityId = checkbox.dataset.entityId;
        const field = checkbox.dataset.field;
        const newValue = checkbox.checked;
        onDirectEdit(entityId, field, newValue);
      }

      // Intercept links
      const link = e.target.closest('a');
      if (link && link.href) {
        e.preventDefault();
        window.open(link.href, '_blank');
      }
    };

    content.addEventListener('click', handleClick);

    return () => {
      content.removeEventListener('click', handleClick);
    };
  }, [entityStore, onDirectEdit]);

  return (
    <div
      ref={containerRef}
      className="editor-preview aide-preview"
      data-testid="preview"
    />
  );
}
