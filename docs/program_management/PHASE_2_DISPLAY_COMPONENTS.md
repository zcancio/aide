# Phase 2: Display Components + Direct Edit

## Overview

**Goal:** The page looks like a real product. Direct editing works.

**Prerequisites:** Phase 1 (vertical slice with FallbackDisplay)

## Display Components

Build in this order - each builds on the previous:

### 1. PageDisplay

Root container with editable title. Wraps all child entities.

```typescript
function PageDisplay({ entity, children }: DisplayProps) {
  const title = entity.props?.title || 'Untitled';

  return (
    <div className="aide-page">
      <EditableField
        value={title}
        entityId={entity.id}
        field="title"
        className="page-title"
      />
      <div className="page-content">
        {children}
      </div>
    </div>
  );
}
```

### 2. CardDisplay

Renders entity props as a styled card with key-value pairs.

```typescript
function CardDisplay({ entity, children }: DisplayProps) {
  const props = entity.props || {};

  return (
    <div className="aide-card">
      {Object.entries(props).map(([key, value]) => (
        <div className="card-field" key={key}>
          <span className="field-label">{formatLabel(key)}</span>
          <EditableField
            value={value}
            entityId={entity.id}
            field={key}
          />
        </div>
      ))}
      {children}
    </div>
  );
}
```

### 3. TableDisplay

Renders child entities as table rows with editable cells.

```typescript
function TableDisplay({ entity, children }: DisplayProps) {
  const childEntities = useChildren(entity.id);
  const columns = inferColumns(childEntities);

  return (
    <table className="aide-table">
      <thead>
        <tr>
          {columns.map(col => <th key={col}>{formatLabel(col)}</th>)}
        </tr>
      </thead>
      <tbody>
        {childEntities.map(child => (
          <tr key={child.id}>
            {columns.map(col => (
              <td key={col}>
                <EditableField
                  value={child.props?.[col]}
                  entityId={child.id}
                  field={col}
                />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

### 4. ChecklistDisplay

Renders child entities as checkable items.

```typescript
function ChecklistDisplay({ entity, children }: DisplayProps) {
  const childEntities = useChildren(entity.id);

  return (
    <div className="aide-checklist">
      {childEntities.map(child => (
        <div className="checklist-item" key={child.id}>
          <input
            type="checkbox"
            checked={child.props?.done === true}
            onChange={(e) => sendUpdate(child.id, 'done', e.target.checked)}
          />
          <EditableField
            value={child.props?.task || child.props?.label}
            entityId={child.id}
            field="task"
          />
        </div>
      ))}
    </div>
  );
}
```

### 5. SectionDisplay

Collapsible section with title and children.

```typescript
function SectionDisplay({ entity, children }: DisplayProps) {
  const [collapsed, setCollapsed] = useState(false);
  const title = entity.props?.title || 'Section';

  return (
    <div className="aide-section">
      <div className="section-header" onClick={() => setCollapsed(!collapsed)}>
        <span className="collapse-icon">{collapsed ? '▸' : '▾'}</span>
        <EditableField
          value={title}
          entityId={entity.id}
          field="title"
          className="section-title"
        />
      </div>
      {!collapsed && (
        <div className="section-content">
          {children}
        </div>
      )}
    </div>
  );
}
```

### 6. EditableField

Click-to-edit component used by all displays.

```typescript
function EditableField({ value, entityId, field, className }: EditableFieldProps) {
  const [editing, setEditing] = useState(false);
  const [localValue, setLocalValue] = useState(String(value ?? ''));
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const commit = () => {
    if (localValue !== String(value ?? '')) {
      sendUpdate(entityId, field, localValue);
    }
    setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className={`editable-input ${className || ''}`}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') setEditing(false);
        }}
      />
    );
  }

  return (
    <span
      className={`editable-value ${className || ''}`}
      onClick={() => { setLocalValue(String(value ?? '')); setEditing(true); }}
    >
      {value ?? '—'}
    </span>
  );
}
```

### 7. Additional Displays

**MetricDisplay** - Large number with label (for counts, totals)
```typescript
function MetricDisplay({ entity }: DisplayProps) {
  const value = entity.props?.value;
  const label = entity.props?.label;
  return (
    <div className="aide-metric">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}
```

**TextDisplay** - Simple text block
```typescript
function TextDisplay({ entity }: DisplayProps) {
  return (
    <div className="aide-text">
      <EditableField value={entity.props?.text} entityId={entity.id} field="text" />
    </div>
  );
}
```

**ListDisplay** - Bulleted/numbered list
```typescript
function ListDisplay({ entity, children }: DisplayProps) {
  const ordered = entity.props?.ordered === true;
  const Tag = ordered ? 'ol' : 'ul';
  return <Tag className="aide-list">{children}</Tag>;
}
```

**ImageDisplay** - Image with optional caption
```typescript
function ImageDisplay({ entity }: DisplayProps) {
  const src = entity.props?.src;
  const caption = entity.props?.caption;
  return (
    <figure className="aide-image">
      {src && <img src={src} alt={caption || ''} />}
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  );
}
```

**GridDisplay** - Grid layout (for football squares, etc.)
```typescript
function GridDisplay({ entity, children }: DisplayProps) {
  const rows = entity.props?.rows || 10;
  const cols = entity.props?.cols || 10;
  return (
    <div
      className="aide-grid"
      style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
    >
      {children}
    </div>
  );
}
```

## Direct Edit Pipeline

### Client → Server Flow

1. User clicks field → `EditableField` enters edit mode
2. User types and commits (Enter/blur)
3. Client sends `entity.update` via WebSocket:
   ```json
   {"type": "direct_edit", "entity_id": "guest_linda", "field": "rsvp", "value": "yes"}
   ```
4. Server applies through reducer (same as AI edits)
5. Server broadcasts delta to all connected clients
6. Telemetry records edit latency

### WebSocket Protocol Extension

Add direct edit message type:

```python
# backend/routes/ws.py
if msg.get("type") == "direct_edit":
    entity_id = msg.get("entity_id")
    field = msg.get("field")
    value = msg.get("value")

    # Build entity.update event
    event = {
        "t": "entity.update",
        "id": entity_id,
        "p": {field: value}
    }

    # Apply through reducer
    result = reduce(snapshot, event)
    if result.accepted:
        snapshot = result.snapshot
        # Broadcast delta
        await websocket.send_text(json.dumps({
            "type": "entity.update",
            "id": entity_id,
            "data": snapshot["entities"][entity_id]
        }))
        # Record telemetry
        tracker.record_direct_edit(latency_ms)
```

## Display Resolution

Update `resolveDisplay` to return actual components:

```typescript
const DISPLAY_MAP: Record<string, ComponentType<DisplayProps>> = {
  page: PageDisplay,
  card: CardDisplay,
  table: TableDisplay,
  checklist: ChecklistDisplay,
  section: SectionDisplay,
  metric: MetricDisplay,
  text: TextDisplay,
  list: ListDisplay,
  image: ImageDisplay,
  grid: GridDisplay,
};

function resolveDisplay(hint: string): ComponentType<DisplayProps> {
  return DISPLAY_MAP[hint] || FallbackDisplay;
}
```

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── AideEntity.tsx           # Updated with resolveDisplay
│   │   ├── EditableField.tsx        # Click-to-edit component
│   │   └── displays/
│   │       ├── PageDisplay.tsx
│   │       ├── CardDisplay.tsx
│   │       ├── TableDisplay.tsx
│   │       ├── ChecklistDisplay.tsx
│   │       ├── SectionDisplay.tsx
│   │       ├── MetricDisplay.tsx
│   │       ├── TextDisplay.tsx
│   │       ├── ListDisplay.tsx
│   │       ├── ImageDisplay.tsx
│   │       ├── GridDisplay.tsx
│   │       └── FallbackDisplay.tsx  # Existing
│   └── styles/
│       └── displays.css             # Styles for all displays

backend/
├── routes/
│   └── ws.py                        # Add direct_edit handling
└── tests/
    └── test_direct_edit.py          # Direct edit tests
```

## Styling

Minimal, clean styles following AIde design system:

```css
/* displays.css */
.aide-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px;
}

.page-title {
  font-size: 28px;
  font-weight: 600;
  margin-bottom: 24px;
  color: #1a1a1a;
}

.aide-card {
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.card-field {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.field-label {
  color: #666;
  font-size: 13px;
}

.aide-table {
  width: 100%;
  border-collapse: collapse;
}

.aide-table th,
.aide-table td {
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid #e5e5e5;
}

.aide-table th {
  font-weight: 500;
  color: #666;
  font-size: 12px;
  text-transform: uppercase;
}

.aide-checklist-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.aide-section {
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 8px 0;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
}

.editable-value {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
}

.editable-value:hover {
  background: #f5f5f5;
}

.editable-input {
  font: inherit;
  padding: 2px 4px;
  border: 1px solid #ddd;
  border-radius: 4px;
  outline: none;
}

.editable-input:focus {
  border-color: #007bff;
}
```

## Implementation Order

1. **EditableField** - Core editing component
2. **PageDisplay** - Root container
3. **CardDisplay** - Basic prop rendering
4. **SectionDisplay** - Collapsible containers
5. **TableDisplay** - Tabular data
6. **ChecklistDisplay** - Interactive checkboxes
7. **Direct Edit WebSocket** - Server-side handling
8. **Additional displays** - Metric, Text, List, Image, Grid
9. **Styling polish** - CSS refinements

## Test Plan

### Unit Tests

```typescript
// EditableField.test.tsx
test('displays value in view mode', () => {
  render(<EditableField value="Hello" entityId="e1" field="name" />);
  expect(screen.getByText('Hello')).toBeInTheDocument();
});

test('enters edit mode on click', () => {
  render(<EditableField value="Hello" entityId="e1" field="name" />);
  fireEvent.click(screen.getByText('Hello'));
  expect(screen.getByRole('textbox')).toHaveFocus();
});

test('commits on Enter', async () => {
  const sendUpdate = jest.fn();
  render(<EditableField value="Hello" entityId="e1" field="name" />);
  fireEvent.click(screen.getByText('Hello'));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'World' } });
  fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
  expect(sendUpdate).toHaveBeenCalledWith('e1', 'name', 'World');
});
```

### Integration Tests

```python
# test_direct_edit.py
async def test_direct_edit_updates_entity():
    async with websocket_client("/ws/aide/test") as ws:
        # First create an entity via message
        ws.send_text(json.dumps({"type": "message", "content": "graduation", "message_id": "1"}))
        # Drain until stream.end
        ...

        # Now send direct edit
        ws.send_text(json.dumps({
            "type": "direct_edit",
            "entity_id": "guest_linda",
            "field": "rsvp",
            "value": "yes"
        }))

        # Should receive entity.update delta
        msg = json.loads(ws.receive_text())
        assert msg["type"] == "entity.update"
        assert msg["id"] == "guest_linda"
        assert msg["data"]["rsvp"] == "yes"

async def test_direct_edit_latency_under_200ms():
    # Measure round-trip time for direct edit
    ...
```

### E2E Test (Manual)

1. Start server, login via dev-login
2. Create new aide with "plan a graduation party"
3. Click on guest name → edit → Enter
4. Verify update appears immediately
5. Toggle checkbox → verify state changes
6. Check telemetry table for direct_edit events

## Checkpoint Criteria

- [ ] All display components render correctly for graduation aide
- [ ] Click any field → inline edit works
- [ ] Enter commits, Escape cancels
- [ ] Checkbox toggles work
- [ ] Direct edits round-trip via WebSocket in <200ms
- [ ] Telemetry records direct_edit events
- [ ] All tests pass

## Measurements

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Direct edit latency | <200ms p95 | Telemetry table |
| Display resolution | 100% correct | Visual inspection with graduation aide |
| Edit commit success | 100% | No reducer rejections on valid edits |
