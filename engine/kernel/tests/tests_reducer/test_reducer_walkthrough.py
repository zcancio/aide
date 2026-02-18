"""
AIde Reducer -- Walkthrough Tests (v3 Unified Entity Model)

Full end-to-end walkthrough scenarios using v3 primitives.
These tests simulate realistic sequences of events that a user
would generate when working with AIde.

Scenarios:
  1. Grocery list: create list, add items, check off, reorganize
  2. Budget tracker: create budget, add expenses, update totals
  3. Task board: create project, add tasks with priority, complete tasks
  4. Football squares: grid-based scenario
  5. Renovation project: meta, styles, schema, entities, blocks all together
"""


from engine.kernel.events import make_event
from engine.kernel.reducer import replay

# ============================================================================
# Scenario 1: Grocery List
# ============================================================================

class TestGroceryListWalkthrough:
    def test_grocery_list_full_flow(self):
        events = [
            # Define schema for grocery items (with items as a Record collection)
            make_event(seq=1, type="schema.create", payload={
                "id": "grocery_item",
                "interface": "interface GroceryItem { name: string; store?: string; checked: boolean; qty?: string; items: Record<string, GroceryItem>; }",
                "render_html": "<li class='item{{#checked}} done{{/checked}}'>{{name}}</li>",
                "render_text": "{{#checked}}[x]{{/checked}}{{^checked}}[ ]{{/checked}} {{name}}",
                "styles": ".item { padding: 8px; } .done { text-decoration: line-through; }",
            }),

            # Set page metadata
            make_event(seq=2, type="meta.update", payload={"title": "Weekend Groceries"}),

            # Create the grocery list entity with initial items
            make_event(seq=3, type="entity.create", payload={
                "id": "weekend_list",
                "_schema": "grocery_item",
                "name": "Weekend List",
                "checked": False,
                "items": {
                    "item_milk": {"name": "Milk", "checked": False, "qty": "2 gallons", "_pos": 1.0, "items": {}},
                    "item_eggs": {"name": "Eggs", "checked": False, "qty": "1 dozen", "_pos": 2.0, "items": {}},
                    "item_bread": {"name": "Bread", "checked": False, "_pos": 3.0, "items": {}},
                },
            }),

            # Add another item
            make_event(seq=4, type="entity.update", payload={
                "id": "weekend_list",
                "items": {
                    "item_butter": {"name": "Butter", "checked": False, "_pos": 4.0},
                },
            }),

            # Check off milk
            make_event(seq=5, type="entity.update", payload={
                "id": "weekend_list",
                "items": {
                    "item_milk": {"checked": True},
                },
            }),

            # Check off eggs
            make_event(seq=6, type="entity.update", payload={
                "id": "weekend_list",
                "items": {
                    "item_eggs": {"checked": True},
                },
            }),

            # Add a block for the list display
            make_event(seq=7, type="block.set", payload={
                "id": "block_list_view",
                "type": "entity_view",
                "parent": "block_root",
                "entity": "weekend_list",
            }),
        ]

        snap = replay(events)

        # Verify schema
        assert "grocery_item" in snap["schemas"]
        assert "GroceryItem" in snap["schemas"]["grocery_item"]["interface"]

        # Verify meta
        assert snap["meta"]["title"] == "Weekend Groceries"

        # Verify entity
        entity = snap["entities"]["weekend_list"]
        assert entity["name"] == "Weekend List"

        items = entity["items"]
        assert items["item_milk"]["checked"] is True
        assert items["item_eggs"]["checked"] is True
        assert items["item_bread"]["checked"] is False
        assert "item_butter" in items
        assert items["item_butter"]["name"] == "Butter"

        # Verify block
        assert "block_list_view" in snap["blocks"]
        assert "block_list_view" in snap["blocks"]["block_root"]["children"]


# ============================================================================
# Scenario 2: Budget Tracker
# ============================================================================

class TestBudgetTrackerWalkthrough:
    def test_budget_tracker_full_flow(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "expense",
                "interface": "interface Expense { description: string; amount: string; category: string; paid: boolean; expenses: Record<string, Expense>; }",
                "render_html": "<tr><td>{{description}}</td><td>{{amount}}</td></tr>",
                "render_text": "{{description}}: {{amount}}",
            }),

            make_event(seq=2, type="meta.update", payload={
                "title": "Home Renovation Budget",
                "visibility": "private",
            }),

            make_event(seq=3, type="style.set", payload={
                "primary_color": "#2563eb",
                "font_family": "Inter",
            }),

            make_event(seq=4, type="entity.create", payload={
                "id": "reno_budget",
                "_schema": "expense",
                "description": "Renovation Budget",
                "amount": "15000",
                "category": "total",
                "paid": False,
                "expenses": {
                    "exp_paint": {
                        "description": "Paint and supplies",
                        "amount": "450",
                        "category": "materials",
                        "paid": True,
                        "expenses": {},
                        "_pos": 1.0,
                    },
                    "exp_flooring": {
                        "description": "Hardwood flooring",
                        "amount": "3200",
                        "category": "materials",
                        "paid": False,
                        "expenses": {},
                        "_pos": 2.0,
                    },
                },
            }),

            # Add labor expense
            make_event(seq=5, type="entity.update", payload={
                "id": "reno_budget",
                "expenses": {
                    "exp_labor": {
                        "description": "Contractor labor",
                        "amount": "5000",
                        "category": "labor",
                        "paid": False,
                        "_pos": 3.0,
                    },
                },
            }),

            # Mark flooring as paid
            make_event(seq=6, type="entity.update", payload={
                "id": "reno_budget",
                "expenses": {
                    "exp_flooring": {"paid": True},
                },
            }),

            # Add an annotation
            make_event(seq=7, type="meta.annotate", payload={
                "note": "Contractor confirmed start date: March 15",
                "pinned": True,
                "author": "user_homeowner",
            }),
        ]

        snap = replay(events)

        assert snap["meta"]["title"] == "Home Renovation Budget"
        assert snap["meta"]["visibility"] == "private"
        assert snap["styles"]["primary_color"] == "#2563eb"

        budget = snap["entities"]["reno_budget"]
        assert budget["description"] == "Renovation Budget"
        assert budget["amount"] == "15000"

        expenses = budget["expenses"]
        assert expenses["exp_paint"]["paid"] is True
        assert expenses["exp_flooring"]["paid"] is True  # marked paid in seq=6
        assert expenses["exp_labor"]["paid"] is False
        assert expenses["exp_labor"]["amount"] == "5000"

        assert len(snap["annotations"]) == 1
        assert "March 15" in snap["annotations"][0]["note"]
        assert snap["annotations"][0]["pinned"] is True


# ============================================================================
# Scenario 3: Task Board (multi-status)
# ============================================================================

class TestTaskBoardWalkthrough:
    def test_task_board_full_flow(self):
        events = [
            make_event(seq=1, type="schema.create", payload={
                "id": "task",
                "interface": "interface Task { title: string; status: string; assignee?: string; priority: string; }",
                "render_html": "<div class='task {{status}}'>{{title}}</div>",
                "render_text": "[{{status}}] {{title}}",
            }),

            make_event(seq=2, type="meta.update", payload={"title": "Sprint 42"}),

            # Create tasks
            make_event(seq=3, type="entity.create", payload={
                "id": "task_auth",
                "_schema": "task",
                "title": "Implement magic link auth",
                "status": "done",
                "assignee": "user_alice",
                "priority": "high",
                "_pos": 1.0,
            }),
            make_event(seq=4, type="entity.create", payload={
                "id": "task_db",
                "_schema": "task",
                "title": "Set up Postgres RLS",
                "status": "in_progress",
                "assignee": "user_bob",
                "priority": "high",
                "_pos": 2.0,
            }),
            make_event(seq=5, type="entity.create", payload={
                "id": "task_ui",
                "_schema": "task",
                "title": "Build chat overlay",
                "status": "todo",
                "priority": "medium",
                "_pos": 3.0,
            }),

            # Move db task to done
            make_event(seq=6, type="entity.update", payload={
                "id": "task_db",
                "status": "done",
            }),

            # Add new task
            make_event(seq=7, type="entity.create", payload={
                "id": "task_deploy",
                "_schema": "task",
                "title": "Deploy to Railway",
                "status": "todo",
                "priority": "high",
                "_pos": 4.0,
            }),

            # Remove a completed task
            make_event(seq=8, type="entity.remove", payload={"id": "task_auth"}),

            # Add layout blocks
            make_event(seq=9, type="block.set", payload={
                "id": "block_title",
                "type": "heading",
                "parent": "block_root",
                "text": "Sprint 42",
            }),
            make_event(seq=10, type="block.set", payload={
                "id": "block_tasks",
                "type": "entity_view",
                "parent": "block_root",
                "entity_type": "task",
            }),
        ]

        snap = replay(events)

        assert snap["meta"]["title"] == "Sprint 42"

        entities = snap["entities"]
        assert entities["task_auth"]["_removed"] is True
        assert entities["task_db"]["status"] == "done"
        assert entities["task_ui"]["status"] == "todo"
        assert entities["task_deploy"]["title"] == "Deploy to Railway"

        # Blocks in order
        root_children = snap["blocks"]["block_root"]["children"]
        assert "block_title" in root_children
        assert "block_tasks" in root_children
        assert root_children.index("block_title") < root_children.index("block_tasks")


# ============================================================================
# Scenario 4: Football Squares (grid)
# ============================================================================

class TestFootballSquaresWalkthrough:
    def test_football_squares_full_flow(self):
        events = [
            make_event(seq=1, type="meta.update", payload={"title": "Super Bowl Squares 2026"}),

            make_event(seq=2, type="entity.create", payload={
                "id": "squares_board",
                "name": "Super Bowl LX",
                "home_team": "Eagles",
                "away_team": "Chiefs",
                "cells": {
                    "_shape": [10, 10],
                    # A few squares claimed
                    "r0_c0": {"owner": "Alice", "paid": True, "_pos": 1.0},
                    "r0_c1": {"owner": "Bob", "paid": False, "_pos": 2.0},
                    "r3_c7": {"owner": "Carol", "paid": True, "_pos": 3.0},
                },
            }),

            # More squares claimed
            make_event(seq=3, type="entity.update", payload={
                "id": "squares_board",
                "cells": {
                    "r5_c5": {"owner": "Dave", "paid": True},
                    "r9_c9": {"owner": "Eve", "paid": False},
                },
            }),

            # Bob pays
            make_event(seq=4, type="entity.update", payload={
                "id": "squares_board",
                "cells": {
                    "r0_c1": {"paid": True},
                },
            }),
        ]

        snap = replay(events)

        board = snap["entities"]["squares_board"]
        assert board["home_team"] == "Eagles"
        assert board["away_team"] == "Chiefs"

        cells = board["cells"]
        assert cells["_shape"] == [10, 10]
        assert cells["r0_c0"]["owner"] == "Alice"
        assert cells["r0_c1"]["paid"] is True  # Bob paid in seq=4
        assert cells["r3_c7"]["owner"] == "Carol"
        assert cells["r5_c5"]["owner"] == "Dave"
        assert cells["r9_c9"]["owner"] == "Eve"


# ============================================================================
# Scenario 5: Full aide setup — meta, style, schema, entities, blocks
# ============================================================================

class TestFullAideSetupWalkthrough:
    def test_complete_aide_from_scratch(self):
        events = [
            # 1. Set metadata
            make_event(seq=1, type="meta.update", payload={
                "title": "Poker League — Season 3",
                "identity": "Weekly poker league tracker for the crew.",
                "visibility": "public",
            }),

            # 2. Apply styles
            make_event(seq=2, type="style.set", payload={
                "primary_color": "#16a34a",
                "bg_color": "#052e16",
                "text_color": "#dcfce7",
                "font_family": "Fira Code",
            }),

            # 3. Create player schema
            make_event(seq=3, type="schema.create", payload={
                "id": "player",
                "interface": "interface Player { name: string; chips: string; wins: string; active: boolean; }",
                "render_html": "<tr><td>{{name}}</td><td>{{chips}}</td><td>{{wins}}</td></tr>",
                "render_text": "{{name}} — chips: {{chips}}, wins: {{wins}}",
            }),

            # 4. Create game schema
            make_event(seq=4, type="schema.create", payload={
                "id": "game",
                "interface": "interface Game { date: string; winner?: string; pot: string; played: boolean; }",
                "render_html": "<div class='game'>{{date}}: {{winner}} won {{pot}}</div>",
                "render_text": "{{date}}: {{winner}}",
            }),

            # 5. Create league entity with players
            make_event(seq=5, type="entity.create", payload={
                "id": "season_3",
                "name": "Season 3",
                "start_date": "2026-01-01",
                "players": {
                    "player_mike": {
                        "_schema": "player",
                        "name": "Mike",
                        "chips": "500",
                        "wins": "2",
                        "active": True,
                        "_pos": 1.0,
                    },
                    "player_sarah": {
                        "_schema": "player",
                        "name": "Sarah",
                        "chips": "750",
                        "wins": "3",
                        "active": True,
                        "_pos": 2.0,
                    },
                    "player_james": {
                        "_schema": "player",
                        "name": "James",
                        "chips": "250",
                        "wins": "0",
                        "active": True,
                        "_pos": 3.0,
                    },
                },
            }),

            # 6. Create game records
            make_event(seq=6, type="entity.create", payload={
                "id": "game_01",
                "_schema": "game",
                "date": "2026-01-08",
                "winner": "Sarah",
                "pot": "150",
                "played": True,
                "_pos": 1.0,
            }),
            make_event(seq=7, type="entity.create", payload={
                "id": "game_02",
                "_schema": "game",
                "date": "2026-01-15",
                "winner": "Mike",
                "pot": "175",
                "played": True,
                "_pos": 2.0,
            }),
            make_event(seq=8, type="entity.create", payload={
                "id": "game_03",
                "_schema": "game",
                "date": "2026-01-22",
                "played": False,
                "pot": "0",
                "_pos": 3.0,
            }),

            # 7. Update Mike's stats after game_02
            make_event(seq=9, type="entity.update", payload={
                "id": "season_3",
                "players": {
                    "player_mike": {"wins": "3"},
                },
            }),

            # 8. Add layout blocks
            make_event(seq=10, type="block.set", payload={
                "id": "block_heading",
                "type": "heading",
                "parent": "block_root",
                "text": "Poker League — Season 3",
            }),
            make_event(seq=11, type="block.set", payload={
                "id": "block_players",
                "type": "entity_view",
                "parent": "block_root",
                "entity": "season_3",
                "view": "players",
            }),
            make_event(seq=12, type="block.set", payload={
                "id": "block_games",
                "type": "entity_view",
                "parent": "block_root",
                "entity_type": "game",
            }),

            # 9. Annotate
            make_event(seq=13, type="meta.annotate", payload={
                "note": "Next game: Jan 22. Mike brings snacks.",
                "pinned": True,
            }),

            # 10. Update schema (add avatar field)
            make_event(seq=14, type="schema.update", payload={
                "id": "player",
                "interface": "interface Player { name: string; chips: string; wins: string; active: boolean; avatar?: string; }",
            }),
        ]

        snap = replay(events)

        # Meta
        assert snap["meta"]["title"] == "Poker League — Season 3"
        assert snap["meta"]["visibility"] == "public"

        # Styles
        assert snap["styles"]["primary_color"] == "#16a34a"
        assert snap["styles"]["bg_color"] == "#052e16"

        # Schemas
        assert "player" in snap["schemas"]
        assert "game" in snap["schemas"]
        assert "avatar?" in snap["schemas"]["player"]["interface"]

        # Season entity
        season = snap["entities"]["season_3"]
        assert season["name"] == "Season 3"
        players = season["players"]
        assert players["player_mike"]["wins"] == "3"  # updated in seq=9
        assert players["player_sarah"]["wins"] == "3"
        assert players["player_james"]["active"] is True

        # Games
        assert snap["entities"]["game_01"]["winner"] == "Sarah"
        assert snap["entities"]["game_02"]["winner"] == "Mike"
        assert snap["entities"]["game_03"]["played"] is False

        # Blocks
        blocks = snap["blocks"]
        root_children = blocks["block_root"]["children"]
        assert "block_heading" in root_children
        assert "block_players" in root_children
        assert "block_games" in root_children

        # Annotations
        assert len(snap["annotations"]) == 1
        assert "Mike brings snacks" in snap["annotations"][0]["note"]
        assert snap["annotations"][0]["pinned"] is True
