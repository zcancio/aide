# AIde Primitive Schemas Reference

This document provides a concise reference for all primitive events used in AIde. Every state change flows through one of these primitives.

## Core Concepts

- **Refs** are `collection_id/entity_id` strings (e.g., `"roster/player_mike"`)
- **IDs** are lowercase, snake_case, alphanumeric + underscores (max 64 chars)
- **All primitives are declarative** — they describe desired state, not actions

## Field Types

| Type | Example | Notes |
|------|---------|-------|
| `string` | `"Mike"` | Required |
| `string?` | `"Mike"` or `null` | Nullable |
| `int` | `20` | Required |
| `int?` | `20` or `null` | Nullable |
| `float` | `9.99` | Required |
| `bool` | `true` | Required |
| `date` | `"2026-02-27"` | ISO 8601 |
| `datetime` | `"2026-02-27T19:00:00Z"` | ISO 8601, UTC |
| `enum` | `{"enum": ["a","b","c"]}` | Fixed values |
| `list` | `{"list": "string"}` | Homogeneous arrays |

## Entity Primitives

### entity.create
Create a new entity in a collection.

```json
{
  "type": "entity.create",
  "payload": {
    "collection": "grocery_list",
    "id": "item_milk",
    "fields": {
      "name": "Milk",
      "checked": false
    }
  }
}
```

- `collection`: target collection ID (required)
- `id`: entity ID (optional, auto-generated if omitted)
- `fields`: field values conforming to collection schema (required)

### entity.update
Update existing entity fields.

```json
{
  "type": "entity.update",
  "payload": {
    "ref": "grocery_list/item_milk",
    "fields": {
      "checked": true
    }
  }
}
```

- `ref`: entity reference (required)
- `fields`: partial field updates (required)

### entity.delete
Delete an entity.

```json
{
  "type": "entity.delete",
  "payload": {
    "ref": "grocery_list/item_milk"
  }
}
```

- `ref`: entity reference (required)

## Collection Primitives

### collection.create
Create a new collection with schema.

```json
{
  "type": "collection.create",
  "payload": {
    "id": "grocery_list",
    "name": "Grocery List",
    "schema": {
      "name": "string",
      "checked": "bool"
    }
  }
}
```

- `id`: collection ID (required)
- `name`: display name (required)
- `schema`: field name → type map (required)

### collection.update
Update collection metadata (name only).

```json
{
  "type": "collection.update",
  "payload": {
    "id": "grocery_list",
    "name": "Shopping List"
  }
}
```

- `id`: collection ID (required)
- `name`: new display name (required)

### collection.delete
Delete a collection and all its entities.

```json
{
  "type": "collection.delete",
  "payload": {
    "id": "grocery_list"
  }
}
```

- `id`: collection ID (required)

## Field Primitives

### field.add
Add a new field to a collection schema.

```json
{
  "type": "field.add",
  "payload": {
    "collection": "grocery_list",
    "field": "store",
    "type": "string?",
    "default": null
  }
}
```

- `collection`: collection ID (required)
- `field`: field name (required)
- `type`: field type (required)
- `default`: default value for existing entities (required)

### field.remove
Remove a field from a collection schema.

```json
{
  "type": "field.remove",
  "payload": {
    "collection": "grocery_list",
    "field": "store"
  }
}
```

- `collection`: collection ID (required)
- `field`: field name (required)

### field.rename
Rename a field in a collection schema.

```json
{
  "type": "field.rename",
  "payload": {
    "collection": "grocery_list",
    "old_name": "checked",
    "new_name": "purchased"
  }
}
```

- `collection`: collection ID (required)
- `old_name`: current field name (required)
- `new_name`: new field name (required)

## Block Primitives

### block.add
Add a markdown content block.

```json
{
  "type": "block.add",
  "payload": {
    "id": "header_intro",
    "content": "# Weekly Grocery Run\n\nShop at Whole Foods every Saturday.",
    "position": 0
  }
}
```

- `id`: block ID (optional, auto-generated if omitted)
- `content`: markdown content (required)
- `position`: insertion index (optional, appends if omitted)

### block.update
Update block content.

```json
{
  "type": "block.update",
  "payload": {
    "id": "header_intro",
    "content": "# Grocery Shopping\n\nUpdated schedule."
  }
}
```

- `id`: block ID (required)
- `content`: new markdown content (required)

### block.delete
Delete a markdown block.

```json
{
  "type": "block.delete",
  "payload": {
    "id": "header_intro"
  }
}
```

- `id`: block ID (required)

### block.move
Reorder a markdown block.

```json
{
  "type": "block.move",
  "payload": {
    "id": "header_intro",
    "position": 2
  }
}
```

- `id`: block ID (required)
- `position`: new position index (required)

## View Primitives

### view.set_sort
Set sort order for a collection view.

```json
{
  "type": "view.set_sort",
  "payload": {
    "collection": "grocery_list",
    "field": "name",
    "direction": "asc"
  }
}
```

- `collection`: collection ID (required)
- `field`: field to sort by (required)
- `direction`: "asc" or "desc" (required)

### view.set_filter
Set filter for a collection view.

```json
{
  "type": "view.set_filter",
  "payload": {
    "collection": "grocery_list",
    "field": "checked",
    "operator": "eq",
    "value": false
  }
}
```

- `collection`: collection ID (required)
- `field`: field to filter on (required)
- `operator`: "eq", "ne", "gt", "gte", "lt", "lte", "contains" (required)
- `value`: filter value (required)

### view.set_group
Set grouping for a collection view.

```json
{
  "type": "view.set_group",
  "payload": {
    "collection": "grocery_list",
    "field": "store"
  }
}
```

- `collection`: collection ID (required)
- `field`: field to group by (required)

### view.clear_sort
Clear sorting from a collection view.

```json
{
  "type": "view.clear_sort",
  "payload": {
    "collection": "grocery_list"
  }
}
```

### view.clear_filter
Clear filter from a collection view.

```json
{
  "type": "view.clear_filter",
  "payload": {
    "collection": "grocery_list"
  }
}
```

### view.clear_group
Clear grouping from a collection view.

```json
{
  "type": "view.clear_group",
  "payload": {
    "collection": "grocery_list"
  }
}
```

## Style Primitives

### style.set_theme
Set global color theme.

```json
{
  "type": "style.set_theme",
  "payload": {
    "theme": "light"
  }
}
```

- `theme`: "light" or "dark" (required)

### style.set_accent
Set accent color.

```json
{
  "type": "style.set_accent",
  "payload": {
    "color": "#007AFF"
  }
}
```

- `color`: hex color code (required)

## Meta Primitives

### meta.set_title
Set aide title.

```json
{
  "type": "meta.set_title",
  "payload": {
    "title": "Weekly Grocery Run"
  }
}
```

- `title`: aide title (required)

### meta.set_description
Set aide description.

```json
{
  "type": "meta.set_description",
  "payload": {
    "description": "Shared shopping list for the household"
  }
}
```

- `description`: aide description (required)

## Relationship Primitives

### relationship.add
Add a relationship between entities.

```json
{
  "type": "relationship.add",
  "payload": {
    "from": "roster/player_mike",
    "to": "schedule/game_feb27",
    "type": "assigned_to"
  }
}
```

- `from`: source entity ref (required)
- `to`: target entity ref (required)
- `type`: relationship type (required)

### relationship.remove
Remove a relationship between entities.

```json
{
  "type": "relationship.remove",
  "payload": {
    "from": "roster/player_mike",
    "to": "schedule/game_feb27",
    "type": "assigned_to"
  }
}
```

- `from`: source entity ref (required)
- `to`: target entity ref (required)
- `type`: relationship type (required)

## Common Patterns

### Creating a new aide from scratch
1. `collection.create` — define the schema
2. `entity.create` (×N) — add initial entities
3. `meta.set_title` — set the title

### Routine updates
1. `entity.update` — modify existing entities
2. `entity.create` — add new entities
3. `entity.delete` — remove entities

### Schema evolution
1. `field.add` — add new field to collection
2. `entity.update` (×N) — populate values in existing entities

### Multi-entity operations
Emit multiple primitives in sequence:
- "Mike's out, Dave's subbing" → two `entity.update` events
- "Got milk and eggs" → two `entity.update` events
