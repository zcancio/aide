"""
Complex multi-turn eval scenarios.

These scenarios are more detailed and closely match real-world usage patterns.
They test dense batch entry, cross-day organization, special events, and
multi-entity queries.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Christmas Week — realistic family planner over multiple turns
# ---------------------------------------------------------------------------

CHRISTMAS_WEEK_REALISTIC = {
    "name": "christmas_week_realistic",
    "description": "Family plans Christmas week in Ann Arbor with day-by-day organization. "
    "Tests tracker pattern (per-day sections), dense batch entry by day, "
    "birthday party as special event, task assignments, and cross-day queries. "
    "Based on real planning dashboard at chris-sam-xmas-elves-25.vercel.app.",
    "turns": [
        # ── Turn 1: Clear week planner request ──
        {
            "message": "christmas 2025 week planner for our family in ann arbor. "
            "show each day as a section: Saturday December 20 through Friday December 26. "
            "under each day we'll add meals, activities, and to-dos",
            "expected_tier": "L4",
            "checks": {
                "creates_page": True,
                "has_day_sections": True,
            },
            "notes": "First message explicitly requests day sections with readable titles. "
            "Should create page with 7 day sections, each titled like 'Saturday, December 20'. "
            "Day sections should use title prop for the header, not separate date/day_name fields. "
            "This ensures proper rendering with visible day headers.",
        },
        # ── Turn 2: Saturday's full plan ──
        {
            "message": "saturday: sam has tennis 9am. dinner is sushi - either nagomi or evergreen, need to decide. "
            "to-do: chris picks up groceries",
            "expected_tier": "L3",
            "checks": {
                "creates_saturday_items": True,
                "min_entities": 3,
            },
            "notes": "Dense single-day entry. Creates under Saturday section: tennis (Sam, 9am), "
            "dinner (sushi options), todo (Chris groceries). Items should be children of the "
            "Saturday section, not siblings at page level.",
        },
        # ── Turn 3: Sunday's dense day ──
        {
            "message": "sunday: samantha yoga 8am, chris fitness center. family outing to greenfield village - "
            "full day trip. dinner: spaghetti and meatballs at home (samantha cooking)",
            "expected_tier": "L3",
            "checks": {
                "creates_sunday_items": True,
                "min_entities": 4,
                "assigns_samantha_cooking": True,
            },
            "notes": "4+ items for Sunday section: yoga (Samantha), fitness (Chris), Greenfield Village (all), "
            "dinner (spaghetti, Samantha cooking). Tests person assignments and 'full day' notation.",
        },
        # ── Turn 4: Monday and Tuesday ──
        {
            "message": "monday: sam tennis 9am, rock climbing afternoon. dinner: pizza from joe's. "
            "tuesday: sam skating 1030am. dinner: smoked bbq ribs (chris cooking)",
            "expected_tier": "L3",
            "checks": {
                "creates_items_both_days": True,
                "min_entities": 5,
            },
            "notes": "Two days in one message. Monday section: tennis, rock climbing, pizza. "
            "Tuesday section: skating, ribs (Chris). Tests multi-day batch parsing.",
        },
        # ── Turn 5: The birthday party (centerpiece event) ──
        {
            "message": "wednesday is the big day - chris's birthday! having 'Chris's Rocking Xmas Eve Birthday Party' "
            "from 3pm to 8pm. menu: carnitas and signature cocktails. expecting about 15 adults",
            "expected_tier": "L3",
            "checks": {
                "creates_party_event": True,
                "has_time_range": True,
                "has_guest_count": True,
            },
            "notes": "The centerpiece event under Wednesday section. Should create a party entity "
            "with: title ('Chris's Rocking Xmas Eve Birthday Party'), time (3-8pm), "
            "menu (carnitas, cocktails), guests (15 adults).",
        },
        # ── Turn 6: Wednesday morning activities ──
        {
            "message": "also wednesday morning before the party - samantha yoga, chris fitness center",
            "expected_tier": "L3",
            "checks": {
                "adds_to_existing_day": True,
            },
            "notes": "Adds morning activities to existing Wednesday section. Should add as siblings "
            "to the party entity, not create a new section.",
        },
        # ── Turn 7: Thursday and Friday ──
        {
            "message": "thursday christmas day - just family time. dinner: leftovers. "
            "friday: sam skating 1030am. dinner: prime rib with all the fixings. "
            "to-do: order the prime rib ahead of time",
            "expected_tier": "L3",
            "checks": {
                "creates_items_both_days": True,
                "creates_task": True,
            },
            "notes": "Thursday section: family time, leftovers. Friday section: skating, prime rib, "
            "plus a todo task. Tests mixing activities, meals, and tasks in one message.",
        },
        # ── Turn 8: Party prep assignments ──
        {
            "message": "party prep tasks for wednesday: samantha handles cocktails, chris does carnitas, "
            "sam on decorations",
            "expected_tier": "L3",
            "checks": {
                "creates_tasks": True,
                "assigns_all_three": True,
            },
            "notes": "Creates 3 party prep tasks with person assignments. Should add to Wednesday "
            "section as to-do items. Tests batch task creation with assignments.",
        },
        # ── Turn 9: Query - what's the busiest day? ──
        {
            "message": "which day has the most going on?",
            "expected_tier": "L4",
            "checks": {
                "identifies_wednesday": True,
                "plain_text": True,
                "no_mutations": True,
            },
            "notes": "L4 query requiring cross-day analysis. Wednesday has: yoga, fitness, "
            "party 3-8pm, 3 party prep tasks. Should identify this as the busiest day.",
        },
        # ── Turn 10: Correction - guest count ──
        {
            "message": "actually the party might be 15-20 people depending on who shows",
            "expected_tier": "L3",
            "checks": {
                "updates_existing": True,
            },
            "notes": "Updates party guest count. Should entity.update the existing party, "
            "NOT create a new one. Tests correction handling.",
        },
        # ── Turn 11: What's still undecided? ──
        {
            "message": "what do we still need to nail down?",
            "expected_tier": "L4",
            "checks": {
                "identifies_open_items": True,
                "plain_text": True,
            },
            "notes": "L4 gap analysis. Should identify: sushi restaurant choice (nagomi vs evergreen), "
            "prime rib order (task unchecked). Tests reasoning about incomplete data.",
        },
    ],
}


# ---------------------------------------------------------------------------
# All complex scenarios
# ---------------------------------------------------------------------------

COMPLEX_SCENARIOS = [
    CHRISTMAS_WEEK_REALISTIC,
]
