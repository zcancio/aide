"""
AIde Eval Scenarios — v3

Scenarios for testing L4 (Opus) first-message synthesis and L3 (Sonnet) compilation.
Uses streaming tool use (mutate_entity / set_relationship), not JSONL.

Routing model:
  - First message (empty snapshot) → L4 (Opus)
  - Every subsequent message → L3 (Sonnet)
  - L3 escalates to L4 for schema evolution / new sections
  - L2 (Haiku) shelved — not in routing path

Each scenario is a multi-turn conversation. Turn 1 always goes to L4.
Subsequent turns go to L3 unless marked as escalation.
"""

# ── Tool Definitions (shared across all tiers) ──────────────────────────────

TOOLS = [
    {
        "name": "mutate_entity",
        "description": "Create, update, or remove an entity",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "update", "remove", "move", "reorder"],
                },
                "id": {
                    "type": "string",
                    "description": "Entity ID (for create)",
                },
                "ref": {
                    "type": "string",
                    "description": "Entity ID (for update/remove/move)",
                },
                "parent": {
                    "type": "string",
                    "description": "'root' or parent entity ID",
                },
                "display": {
                    "type": "string",
                    "enum": [
                        "page", "section", "card", "list", "table",
                        "checklist", "grid", "metric", "text", "image",
                    ],
                },
                "props": {"type": "object"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "set_relationship",
        "description": "Set, remove, or constrain a relationship between entities",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["set", "remove", "constrain"],
                },
                "from": {"type": "string"},
                "to": {"type": "string"},
                "type": {"type": "string"},
                "cardinality": {
                    "type": "string",
                    "enum": ["one_to_one", "many_to_one", "many_to_many"],
                },
            },
            "required": ["action", "type"],
        },
    },
]

# ── Model Configuration ─────────────────────────────────────────────────────

MODELS = {
    "L4": "claude-opus-4-5-20251101",
    "L3": "claude-sonnet-4-5-20250929",
}

TEMPERATURE = {
    "L4": 0.2,  # First message: slight exploration
    "L3": 0,    # Compilation: deterministic
}

# ── Scenarios ────────────────────────────────────────────────────────────────

SCENARIOS = [
    # ── 1. Grocery List (flat list → checklist evolution) ────────────────
    {
        "id": "grocery_list",
        "name": "Grocery List",
        "description": "Basic flat list. Tests L4 first-message synthesis, L3 updates, pattern evolution to checklist.",
        "pattern": "flat_list",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "We need milk, eggs, that sourdough from Whole Foods, chicken for taco Tuesday, tortillas, cheese, salsa, lettuce, and olive oil.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 10, "max": 15},  # page + section + 9 items
                },
                "expect_entities": [
                    {"id_pattern": "item_*", "min_count": 9},
                ],
                "expect_display": "list",
                "notes": "L4 creates flat list. Sourdough should have store: 'Whole Foods'. Should NOT over-scaffold with categories.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Got the milk and eggs.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "L3 resolves 'milk' and 'eggs' to entity refs, marks done. Pattern evolves flat list → checklist (adds boolean field).",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Add bananas and Greek yogurt.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "L3 creates two new child entities under existing section.",
            },
            {
                "turn": 4,
                "tier": "L3",
                "type": "query",
                "message": "What do I still need to get?",
                "expect_tool_calls": {},  # Pure query — text only
                "expect_text": True,
                "notes": "L3 reads snapshot, filters unchecked items, responds in text. No tool calls.",
            },
        ],
    },

    # ── 2. Poker League (roster + timeline + ledger) ─────────────────────
    {
        "id": "poker_league",
        "name": "Poker League",
        "description": "Multi-section aide. Tests L4 pattern classification (roster + timeline + ledger), L3 entity updates.",
        "pattern": "roster + timeline + ledger",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "I run a poker league. 8 guys, we play every other Thursday at someone's house. We rotate who hosts and who brings snacks. The players are Mike, Dave, Chris, James, Zach, Tom, Ryan, and Jake. Next game is Feb 27 at Dave's. Mike's on snacks. Current standings: Zach 340, Chris 310, Dave 280, Mike 260, Tom 240, James 195, Ryan 180, Jake 150.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 12, "max": 20},  # page + 3 sections + 8 players + schedule + standings
                },
                "expect_sections": ["players", "games", "standings"],
                "expect_entities": [
                    {"id_pattern": "player_*", "min_count": 8},
                ],
                "expect_display": "table",
                "notes": "L4 must create 3 sections. Players as table, not 8 individual cards. Standings with points as table sorted desc.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Mike's out this week, Ryan is hosting instead.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 1, "max": 3},
                },
                "notes": "L3 updates game entity: host → Ryan. May update Mike's status.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Game night results: Zach +80, Chris +40, Dave -30, Tom -20, Ryan -25, James -15, Jake -30.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 7, "max": 8},
                },
                "notes": "L3 updates standings for 7 players. Mike was absent, no update.",
            },
            {
                "turn": 4,
                "tier": "L3",
                "type": "query",
                "message": "Who's in the lead?",
                "expect_tool_calls": {},
                "expect_text": True,
                "notes": "L3 reads standings, reports leader. Should include top 2-3 with point totals.",
            },
        ],
    },

    # ── 3. Graduation Party (card + table + checklist) ───────────────────
    {
        "id": "graduation_party",
        "name": "Graduation Party",
        "description": "Multi-section with diverse display types. Tests L4 display hint selection, L3 multi-intent.",
        "pattern": "card + roster + ledger + flat_list",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Planning Sophie's college graduation party. Ceremony is May 22 at 10am at UC Davis. Party at our house after. Guest list: Aunt Linda (yes, bringing potato salad, driving from Portland), Uncle Steve (yes, vegetarian), Cousin James (pending). Need to book venue, order cake, send invitations.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 8, "max": 18},
                },
                "expect_sections": ["ceremony", "guests", "food", "todos"],
                "notes": "Ceremony as card, guests as table, food as table, todos as checklist. Linda's RSVP is yes, Steve is vegetarian, James is pending.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Aunt Linda RSVPed yes, she's bringing potato salad and driving from Portland.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 1, "max": 3},
                },
                "notes": "Linda already RSVPed in turn 1. L3 should recognize duplicate or update food item. Tests entity resolution.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "James confirmed! He's bringing his girlfriend too. Her name is Mia.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 3},
                },
                "notes": "Update James RSVP + create Mia as new guest. Tests multi-operation from one message.",
            },
            {
                "turn": 4,
                "tier": "L3",
                "type": "query",
                "message": "Who hasn't RSVPed yet?",
                "expect_tool_calls": {},
                "expect_text": True,
                "notes": "Negation query. L3 must filter for non-confirmed guests. Common failure mode for smaller models.",
            },
        ],
    },

    # ── 4. Football Squares (grid pattern) ───────────────────────────────
    {
        "id": "football_squares",
        "name": "Super Bowl Squares",
        "description": "Grid pattern. Tests L4 grid pre-population (100 cells), L3 coordinate translation.",
        "pattern": "grid + roster + ledger",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Set up a Super Bowl squares pool. Chiefs vs 49ers, $20 per square.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 100, "max": 115},  # 100 cells + section + page + metadata
                },
                "expect_grid": {
                    "rows": 10,
                    "cols": 10,
                    "cell_id_pattern": "cell_{row}_{col}",
                },
                "notes": "L4 must pre-populate all 100 cells. Section entity has _rows: 10, _cols: 10. Cell IDs are cell_0_0 through cell_9_9.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Mike wants the first 5 squares in row 1. Sarah wants the first 5 in row 2.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 10, "max": 10},
                },
                "notes": "L3 translates 'row 1' to row index, updates 5 cells for Mike and 5 for Sarah. cell_0_0 through cell_0_4 and cell_1_0 through cell_1_4.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Dave claims row 3 column 4, row 6 column 8, and row 9 column 2.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 3, "max": 3},
                },
                "notes": "L3 translates three coordinate pairs to cell_2_3, cell_5_7, cell_8_1 (zero-indexed).",
            },
            {
                "turn": 4,
                "tier": "L3",
                "type": "query",
                "message": "How many squares are claimed?",
                "expect_tool_calls": {},
                "expect_text": True,
                "notes": "L3 counts cells with non-null owner prop.",
            },
        ],
    },

    # ── 5. Chess Game (grid pattern, complex coordinate translation) ─────
    {
        "id": "chess_game",
        "name": "Chess Game",
        "description": "8x8 grid with piece state. Tests L4 chess initialization, L3 algebraic notation translation.",
        "pattern": "grid",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Start a chess game. I'm playing white against my friend Alex.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 64, "max": 72},  # 64 cells + page + section + metadata
                },
                "expect_grid": {
                    "rows": 8,
                    "cols": 8,
                    "row_labels": ["8", "7", "6", "5", "4", "3", "2", "1"],
                    "col_labels": ["a", "b", "c", "d", "e", "f", "g", "h"],
                },
                "notes": "All 64 cells with piece and color props. Standard opening position. Row 0 = rank 8 (black back rank), row 7 = rank 1 (white back rank).",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "e4",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "White pawn from e2 to e4. L3 must: clear cell_6_4 (e2), set cell_4_4 (e4) to white pawn. Coordinate translation: col e = index 4, rank 4 → row 4 (from top, rank 8 = row 0).",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Alex plays e5",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "Black pawn from e7 to e5. Clear cell_1_4 (e7), set cell_3_4 (e5).",
            },
            {
                "turn": 4,
                "tier": "L3",
                "message": "Nf3",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "White knight from g1 to f3. Clear cell_7_6 (g1), set cell_5_5 (f3).",
            },
        ],
    },

    # ── 6. Group Trip (roster + timeline + ledger + flat list) ───────────
    {
        "id": "group_trip",
        "name": "Ski Trip",
        "description": "4-section aide. Tests L4 multi-pattern synthesis, L3 cross-section operations.",
        "pattern": "roster + timeline + ledger + flat_list",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Planning a ski trip to Tahoe. Me, Sarah, and Jess. March 14-17. We booked an Airbnb for $1,200 total ($400 each). Sarah's driving. I need to figure out lift tickets — probably $150/day per person. Jess is vegetarian.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 8, "max": 20},
                },
                "expect_sections": ["travelers", "schedule", "expenses", "packing"],
                "notes": "Travelers as roster (3 people with dietary/transport notes), schedule as timeline, expenses as ledger with Airbnb entry, packing as flat list (may be empty initially).",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Jess can't come anymore. It's just me and Sarah now. Airbnb is $600 each.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 4},
                },
                "notes": "Remove Jess (soft delete), update Airbnb expense split. Tests entity removal + field update.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Add lift tickets to expenses. 3 days at $150/day for 2 people = $900 total, $450 each.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 1, "max": 2},
                },
                "notes": "Create expense entity under expenses section.",
            },
        ],
    },

    # ── 7. Escalation Test ───────────────────────────────────────────────
    {
        "id": "escalation",
        "name": "L3 → L4 Escalation",
        "description": "Tests L3 recognizing when it needs L4 help for structural changes.",
        "pattern": "flat_list → flat_list + ledger",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Packing list for Tahoe: ski jacket, goggles, thermal underwear, sunscreen, hand warmers.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 6, "max": 8},
                },
                "notes": "Simple flat list with 5 items.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "Mark ski jacket as packed.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 1, "max": 1},
                },
                "notes": "Simple update. Adds done/packed boolean.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Actually, let's also track expenses for this trip. Airbnb was $1200, lift tickets $900.",
                "expect_escalation": True,
                "notes": "L3 should recognize this needs a new section (ledger pattern). Should escalate to L4 rather than attempting schema synthesis itself.",
            },
        ],
    },

    # ── 8. Pattern Evolution Test ────────────────────────────────────────
    {
        "id": "pattern_evolution",
        "name": "Flat List → Table Evolution",
        "description": "Tests organic pattern evolution from flat list to table via field addition.",
        "pattern": "flat_list → table",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Christmas shopping list: Nintendo Switch, Lego set, cookbook, scarf, candles.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 6, "max": 8},
                },
                "notes": "Starts as simple flat list.",
            },
            {
                "turn": 2,
                "tier": "L3",
                "message": "The Switch is for Alex, $300 at Target. The Lego set is for Sam, $80 at Amazon.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 2, "max": 2},
                },
                "notes": "Adds recipient, price, store fields to existing entities. Pattern evolves flat list → table as field count grows. L3 handles this — no escalation needed.",
            },
            {
                "turn": 3,
                "tier": "L3",
                "message": "Cookbook for Mom, $25. Scarf for Dad, $40. Candles for Sarah, $15.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 3, "max": 3},
                },
                "notes": "Continues field enrichment across remaining entities.",
            },
            {
                "turn": 4,
                "tier": "L3",
                "type": "query",
                "message": "How much am I spending total?",
                "expect_tool_calls": {},
                "expect_text": True,
                "notes": "L3 sums price fields across entities.",
            },
        ],
    },

    # ── 9. Voice Quality Test ────────────────────────────────────────────
    {
        "id": "voice_quality",
        "name": "Voice Narration Quality",
        "description": "Tests voice output quality during L4 first-message synthesis. Graded by reading.",
        "pattern": "roster + timeline + ledger",
        "turns": [
            {
                "turn": 1,
                "tier": "L4",
                "message": "Wedding planning for June 15. Venue is The Grand Ballroom. 80 guests expected. Budget is $25,000. Catering, photography, flowers, DJ, and cake still need to be booked. Bridesmaids: Amy, Beth, and Carol. Groomsmen: Dan, Eric, and Frank.",
                "expect_tool_calls": {
                    "mutate_entity": {"min": 15, "max": 30},
                },
                "expect_voice": {
                    "rules": [
                        "No first person ('I created', 'I set up')",
                        "No encouragement ('Congratulations!', 'How exciting!')",
                        "No emojis",
                        "State reflections only ('Wedding: June 15, The Grand Ballroom.')",
                        "Interleaved between tool calls, not all at end",
                        "Under 100 characters per voice line",
                    ],
                },
                "notes": "Quality eval. Check that text blocks are brief, infrastructure-toned, and interleaved with tool calls.",
            },
        ],
    },
]
