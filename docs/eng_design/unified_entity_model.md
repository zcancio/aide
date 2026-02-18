# Unified Entity Model

**Status:** Draft v3
**Date:** February 2026

## Summary

Everything is an entity. Schemas define types using **TypeScript interfaces** — the native language LLMs know best. Rendering is multi-channel: HTML for web, text/unicode for SMS and terminals. Schemas are parsed by tree-sitter in both Python and JavaScript.

## Core Concepts

### Schemas Are TypeScript Interfaces

A schema defines:
1. **Interface** — TypeScript interface (the type definition)
2. **Render templates** — Mustache templates for HTML and text
3. **Styles** — CSS for HTML rendering

```json
{
  "schemas": {
    "GroceryList": {
      "interface": "interface GroceryList { title: string; default_store?: string; items: Record<string, GroceryItem>; }",
      "render_html": "<div class=\"list\"><h2>{{title}}</h2><ul>{{>items}}</ul></div>",
      "render_text": "{{title}}\n─────────\n{{>items}}",
      "styles": ".list { padding: 16px; }"
    },
    "GroceryItem": {
      "interface": "interface GroceryItem { name: string; checked: boolean; store?: string; }",
      "render_html": "<li class=\"item {{#checked}}done{{/checked}}\"><input type=\"checkbox\" {{#checked}}checked{{/checked}} /><span>{{name}}</span></li>",
      "render_text": "{{#checked}}✓{{/checked}}{{^checked}}○{{/checked}} {{name}}",
      "styles": ".item { padding: 8px; } .item.done { opacity: 0.5; text-decoration: line-through; }"
    }
  }
}
```

### Why TypeScript?

1. **LLM fluency** — LLMs are trained extensively on TypeScript, they write it natively
2. **Browser-compatible** — Tree-sitter parses it in both Python and JavaScript
3. **Rich type system** — Unions, optionals, generics already defined
4. **No translation layer** — The interface IS the schema, no compilation step

### Multi-Channel Rendering

Schemas define two render templates:

| Channel | Template | Use Case |
|---------|----------|----------|
| `render_html` | HTML + Mustache | Web browser |
| `render_text` | Unicode + Mustache | SMS, terminal, Slack |

`styles` only applies to HTML rendering.

**Example output:**

HTML:
```html
<div class="list">
  <h2>Groceries</h2>
  <ul>
    <li class="item">Milk</li>
    <li class="item done">Eggs</li>
  </ul>
</div>
```

Text:
```
Groceries
─────────
○ Milk
✓ Eggs
```

### Entities Have Schemas

`_schema` on an entity means "I am this type" — like a class instance:

```json
{
  "entities": {
    "grocery_list": {
      "_schema": "GroceryList",
      "title": "Weekly Groceries",
      "default_store": "Whole Foods",
      "items": {
        "item_milk": { "name": "Milk", "checked": false, "_pos": 1.0 },
        "item_eggs": { "name": "Eggs", "checked": true, "_pos": 2.0 }
      }
    }
  }
}
```

- `grocery_list` IS a `GroceryList`
- Fields are validated against the parsed TypeScript interface
- `items` is `Record<string, GroceryItem>` — each value conforms to `GroceryItem`

### TypeScript Type Mappings

| TypeScript | JSON Value | Notes |
|------------|------------|-------|
| `string` | `"text"` | Required string |
| `string?` or `string \| undefined` | `"text"` or absent | Optional |
| `string \| null` | `"text"` or `null` | Nullable |
| `number` | `5` or `4.99` | Integer or float |
| `boolean` | `true` / `false` | Boolean |
| `Date` | `"2026-02-27"` | ISO 8601 date string |
| `"a" \| "b" \| "c"` | `"a"` | Union/enum |
| `string[]` | `["a", "b"]` | Array |
| `Record<string, T>` | `{...}` | Child collection |

### Ordering with Fractional Indexing

Children use `_pos` for ordering (fractional indexing):

```json
{
  "items": {
    "item_milk": { "name": "Milk", "_pos": 1.0 },
    "item_eggs": { "name": "Eggs", "_pos": 2.0 },
    "item_bread": { "name": "Bread", "_pos": 3.0 }
  }
}
```

**Insert between milk and eggs:** new item with `_pos: 1.5`
**Move bread before milk:** set `bread._pos = 0.5`

Benefits:
- Single-field update to reorder (no cascade)
- Insert anywhere without shifting
- Concurrent-edit safe

## Parsing with tree-sitter

Both Python (backend) and JavaScript (browser) use tree-sitter to parse TypeScript interfaces.

### Python

```python
from tree_sitter import Parser
import tree_sitter_typescript as ts

parser = Parser(ts.language_typescript())

def parse_interface(code: str) -> dict[str, str]:
    """Parse TypeScript interface, return field name -> type mapping."""
    tree = parser.parse(code.encode())
    fields = {}

    for node in tree.root_node.children:
        if node.type == "interface_declaration":
            for child in node.children:
                if child.type == "object_type":
                    for prop in child.children:
                        if prop.type == "property_signature":
                            name = prop.child_by_field_name("name").text.decode()
                            type_node = prop.child_by_field_name("type")
                            fields[name] = type_node.text.decode()
    return fields

# Example
parse_interface("interface Foo { name: string; checked: boolean; }")
# => {"name": "string", "checked": "boolean"}
```

### JavaScript (Browser)

```javascript
import Parser from 'web-tree-sitter';

await Parser.init();
const parser = new Parser();
const TypeScript = await Parser.Language.load('/tree-sitter-typescript.wasm');
parser.setLanguage(TypeScript);

function parseInterface(code) {
    const tree = parser.parse(code);
    const fields = {};
    // Same tree-walking logic as Python
    return fields;
}
```

Dependencies:
- Python: `pip install tree-sitter tree-sitter-typescript`
- Browser: `web-tree-sitter` + WASM file (~500KB)

Cache parsed results per schema — parse once, validate many times.

## Schema Structure

```typescript
Schema {
  interface: string          // TypeScript interface source
  render_html?: string       // Mustache template for HTML
  render_text?: string       // Mustache template for text/unicode
  styles?: string            // CSS (HTML only)
}
```

### Example: Full Schema

```json
{
  "GroceryList": {
    "interface": "interface GroceryList { title: string; default_store?: string; items: Record<string, GroceryItem>; }",
    "render_html": "<div class=\"grocery-list\"><h2>{{title}}</h2>{{#default_store}}<p class=\"store\">Default: {{default_store}}</p>{{/default_store}}<div class=\"items\">{{>items}}</div></div>",
    "render_text": "{{title}}{{#default_store}} ({{default_store}}){{/default_store}}\n{{>items}}",
    "styles": ".grocery-list { padding: 16px; } .store { color: #666; font-size: 14px; }"
  }
}
```

## Entity Structure

```typescript
Entity {
  // Type
  _schema?: string           // "I am this type"

  // Data (user-defined fields from schema)
  [field: string]: any       // validated against parsed interface

  // Ordering (for entities in a collection)
  _pos?: number              // fractional index for sort order

  // View config (for entities with children)
  _view?: ViewConfig         // how to lay out children

  // Internal
  _removed?: boolean
  _created_seq?: number
  _updated_seq?: number
}

ViewConfig {
  type: "list" | "table"
  sort?: { field: string, direction: "asc" | "desc" }
  filter?: { field: string, operator: string, value: any }
}
```

## Addressing

Entities are addressed by path:

- `grocery_list` — top-level entity
- `grocery_list/items/item_milk` — child in `items` field
- `poker_league/players/player_mike` — nested child

The path includes the field name for children: `entity/field/child_id`

## Snapshot Structure

```json
{
  "version": 3,
  "meta": {
    "title": "My Aide",
    "identity": "A grocery list tracker"
  },
  "schemas": {
    "GroceryList": {
      "interface": "interface GroceryList { title: string; items: Record<string, GroceryItem>; }",
      "render_html": "...",
      "render_text": "...",
      "styles": "..."
    },
    "GroceryItem": {
      "interface": "interface GroceryItem { name: string; checked: boolean; }",
      "render_html": "...",
      "render_text": "...",
      "styles": "..."
    }
  },
  "entities": {
    "grocery_list": {
      "_schema": "GroceryList",
      "title": "Weekly Groceries",
      "items": {
        "item_milk": { "name": "Milk", "checked": false, "_pos": 1.0 },
        "item_eggs": { "name": "Eggs", "checked": true, "_pos": 2.0 }
      }
    }
  },
  "blocks": {
    "block_root": { "type": "root", "children": ["block_list"] },
    "block_list": { "type": "entity_view", "source": "grocery_list" }
  },
  "styles": {
    "primary_color": "#2d3748",
    "bg_color": "#fafaf9",
    "font_family": "Inter"
  }
}
```

## Primitives

### Schema Primitives

#### schema.create

```json
{
  "type": "schema.create",
  "payload": {
    "id": "GroceryItem",
    "interface": "interface GroceryItem { name: string; checked: boolean; }",
    "render_html": "<li class=\"item\">{{name}}</li>",
    "render_text": "{{#checked}}✓{{/checked}}{{^checked}}○{{/checked}} {{name}}",
    "styles": ".item { padding: 8px; }"
  }
}
```

#### schema.update

```json
{
  "type": "schema.update",
  "payload": {
    "id": "GroceryItem",
    "interface": "interface GroceryItem { name: string; checked: boolean; store?: string; }",
    "render_html": "<li class=\"item\">{{name}}{{#store}} ({{store}}){{/store}}</li>"
  }
}
```

Replaces interface and/or templates. Omitted fields unchanged.

#### schema.remove

```json
{
  "type": "schema.remove",
  "payload": { "id": "GroceryItem" }
}
```

Fails if any entities reference it.

### Entity Primitives

#### entity.create

```json
{
  "type": "entity.create",
  "payload": {
    "id": "grocery_list",
    "_schema": "GroceryList",
    "title": "Weekly Groceries",
    "items": {
      "item_milk": { "name": "Milk", "checked": false, "_pos": 1.0 }
    }
  }
}
```

#### entity.update

Update fields and/or children:

```json
{
  "type": "entity.update",
  "payload": {
    "id": "grocery_list",
    "title": "This Week's Groceries",
    "items": {
      "item_milk": { "checked": true },
      "item_bread": { "name": "Bread", "checked": false, "_pos": 1.5 },
      "item_eggs": null
    }
  }
}
```

- `item_milk`: update existing
- `item_bread`: create new (didn't exist)
- `item_eggs`: `null` removes it
- Other children untouched

Path syntax for direct child update:

```json
{
  "type": "entity.update",
  "payload": {
    "id": "grocery_list/items/item_milk",
    "checked": true
  }
}
```

#### entity.remove

```json
{
  "type": "entity.remove",
  "payload": { "id": "grocery_list" }
}
```

Soft-deletes entity and all nested children.

## Render Templates

### Mustache Syntax

```mustache
{{name}}                              <!-- field interpolation -->
{{#checked}}done{{/checked}}          <!-- truthy section -->
{{^checked}}pending{{/checked}}       <!-- falsy section -->
{{>items}}                            <!-- render child collection -->
```

### Child Collection Rendering

`{{>fieldname}}` renders a child collection:

```json
{
  "GroceryList": {
    "interface": "interface GroceryList { title: string; items: Record<string, GroceryItem>; }",
    "render_html": "<div><h2>{{title}}</h2><ul>{{>items}}</ul></div>",
    "render_text": "{{title}}\n{{>items}}"
  }
}
```

The renderer:
1. Gets children from `items` field
2. Sorts by `_pos`
3. Renders each child using `GroceryItem.render_html` or `render_text`
4. Wraps in layout per `_view.type`

### Available Variables

- All fields from interface
- `_id` — entity ID
- `_pos` — position (for sorted display)
- `_index` — computed index after sorting

## Examples

### Grocery List

```json
{
  "schemas": {
    "GroceryList": {
      "interface": "interface GroceryList { title: string; items: Record<string, GroceryItem>; }",
      "render_html": "<div class=\"list\"><h2>{{title}}</h2><ul>{{>items}}</ul></div>",
      "render_text": "{{title}}\n─────────\n{{>items}}",
      "styles": ".list { padding: 16px; }"
    },
    "GroceryItem": {
      "interface": "interface GroceryItem { name: string; checked: boolean; }",
      "render_html": "<li class=\"{{#checked}}done{{/checked}}\">{{name}}</li>",
      "render_text": "{{#checked}}✓{{/checked}}{{^checked}}○{{/checked}} {{name}}",
      "styles": ".done { text-decoration: line-through; opacity: 0.5; }"
    }
  },
  "entities": {
    "grocery_list": {
      "_schema": "GroceryList",
      "title": "Weekly Groceries",
      "items": {
        "item_milk": { "name": "Milk", "checked": false, "_pos": 1.0 },
        "item_eggs": { "name": "Eggs", "checked": true, "_pos": 2.0 }
      }
    }
  }
}
```

**HTML output:**
```html
<div class="list">
  <h2>Weekly Groceries</h2>
  <ul>
    <li class="">Milk</li>
    <li class="done">Eggs</li>
  </ul>
</div>
```

**Text output:**
```
Weekly Groceries
─────────
○ Milk
✓ Eggs
```

### Poker League (Multiple Child Collections)

```json
{
  "schemas": {
    "League": {
      "interface": "interface League { name: string; season: string; players: Record<string, Player>; games: Record<string, Game>; }",
      "render_html": "<div class=\"league\"><h1>{{name}}</h1><p>{{season}}</p><div class=\"sections\"><div><h2>Players</h2>{{>players}}</div><div><h2>Games</h2>{{>games}}</div></div></div>",
      "render_text": "{{name}} — {{season}}\n\nPlayers:\n{{>players}}\n\nGames:\n{{>games}}",
      "styles": ".league { padding: 16px; } .sections { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }"
    },
    "Player": {
      "interface": "interface Player { name: string; wins: number; status: 'active' | 'out' | 'sub'; }",
      "render_html": "<div class=\"player {{status}}\"><span>{{name}}</span><span class=\"badge\">{{status}}</span></div>",
      "render_text": "{{name}} ({{wins}}W) {{status}}",
      "styles": ".player { padding: 8px; } .player.out { opacity: 0.5; }"
    },
    "Game": {
      "interface": "interface Game { date: string; host: string; winner?: string; }",
      "render_html": "<div class=\"game\"><span class=\"date\">{{date}}</span><span class=\"host\">@ {{host}}</span>{{#winner}}<span class=\"winner\">Winner: {{winner}}</span>{{/winner}}</div>",
      "render_text": "{{date}} @ {{host}}{{#winner}} → {{winner}}{{/winner}}",
      "styles": ".game { padding: 8px; } .date { font-weight: 500; }"
    }
  },
  "entities": {
    "poker_league": {
      "_schema": "League",
      "name": "Thursday Night Poker",
      "season": "Spring 2026",
      "players": {
        "player_mike": { "name": "Mike", "wins": 3, "status": "active", "_pos": 1.0 },
        "player_dave": { "name": "Dave", "wins": 2, "status": "active", "_pos": 2.0 }
      },
      "games": {
        "game_1": { "date": "2026-02-20", "host": "Mike", "winner": "Dave", "_pos": 1.0 },
        "game_2": { "date": "2026-02-27", "host": "Dave", "_pos": 2.0 }
      }
    }
  }
}
```

## Migration from v2

1. **Convert fields to interface** — `{ "fields": { "name": "str" } }` → `{ "interface": "interface X { name: string; }" }`
2. **Rename render** — `render` → `render_html`
3. **Add render_text** — create text/unicode version of each template
4. **Update version** — `"version": 2` → `"version": 3`

## Summary

- **TypeScript interfaces** — schemas defined in a language LLMs know natively
- **tree-sitter parsing** — same parser in Python and JavaScript
- **Multi-channel rendering** — `render_html` for web, `render_text` for SMS/terminal
- **`_schema` = "I am this type"** — entities declare their type
- **`Record<string, T>`** — typed child collections
- **Fractional indexing** — `_pos` for ordering
- **Tensor shapes** — `_shape` generates predictable keys for grids
