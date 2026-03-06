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
# Christmas Week Ideal — matches mock_christmas_entity_state_ideal.json
# ---------------------------------------------------------------------------

CHRISTMAS_WEEK_IDEAL = {
    "name": "christmas_week_ideal",
    "description": "Family plans Christmas week in Ann Arbor. Messages designed to produce "
    "the exact entity structure in mock_christmas_entity_state_ideal.json. "
    "Tests day-by-day section structure with Activities (table), Meals (table), and To-Do (checklist) per day.",
    "expected_final_state": "evals/scripts/mock_christmas_entity_state_ideal.json",
    "turns": [
        # ── Turn 1: Create week planner with 7 day sections ──
        {
            "message": "christmas 2025 week planner for our family in ann arbor. "
            "show each day as a section: Saturday December 20 through Friday December 26. "
            "under each day we'll add meals, activities, and to-dos",
            "expected_tier": "L4",
            "checks": {
                "creates_page": True,
                "has_day_sections": True,
                "section_count": 7,
            },
            "notes": "Creates page with 7 sections. Each section has title like 'Saturday, Dec 20'. "
            "Each section should have Activities (table), Meals (table), To-Do (checklist) children.",
        },
        # ── Turn 2: Saturday activities ──
        {
            "message": "saturday: skating lessons 9-11am, henry has rock climbing 12:45-2:15pm, "
            "chris massage 3:15-4:15pm",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 3,
            },
            "notes": "Saturday activities: skating lessons, rock climbing (Henry), massage (Chris). "
            "Items go in sat_activities table.",
        },
        # ── Turn 3: Saturday dinner and airport pickup ──
        {
            "message": "saturday dinner is spaghetti and meatballs, chris and henry will make it. "
            "also need to pick up allan at airport around 7pm",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 3,
            },
            "notes": "Adds dinner to sat_meals, airport pickup to sat_activities (with DTW map link), "
            "and cooking task to sat_todos.",
        },
        # ── Turn 4: Sunday activities ──
        {
            "message": "sunday: chris barn tennis 6:30-8am, samantha yoga at 9, kids tennis class 12-1pm",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 3,
            },
            "notes": "Sunday activities in sun_activities table.",
        },
        # ── Turn 5: Sunday meals ──
        {
            "message": "sunday lunch at nagomi or evergreen, dinner is spaghetti & jumbo meatballs, "
            "salad, and chicken wings",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 4,
            },
            "notes": "Sunday meals: lunch (Nagomi with map link), dinner items. Each menu item separate entity.",
        },
        # ── Turn 6: Sunday todo ──
        {
            "message": "chris needs to pick up prime rib and pork shoulder on sunday",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 1,
            },
            "notes": "Single todo item in sun_todos checklist.",
        },
        # ── Turn 7: Monday activities ──
        {
            "message": "monday: kids drop off at leslie science nature center 8:30am, "
            "chris trainer 11am-12pm, sam yoga 12-1pm, kids pickup 3:30pm, "
            "chris done with work 5pm, chris & nicole arrive evening",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 6,
            },
            "notes": "Dense Monday activities. Leslie Science Center items get map links. "
            "Some items marked done (drop off, pickup, work done, arrive).",
        },
        # ── Turn 8: Monday dinner menu ──
        {
            "message": "monday dinner: smoked bbq ribs & chicken, baked beans, mac and cheese, "
            "coleslaw, gf cornbread",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 5,
            },
            "notes": "5 dinner menu items for Monday in mon_meals table.",
        },
        # ── Turn 9: Monday todos ──
        {
            "message": "monday todos: chris smoke ribs & chicken, sam make gf cornbread mac and cheese coleslaw",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 2,
            },
            "notes": "Two cooking tasks in mon_todos checklist.",
        },
        # ── Turn 10: Tuesday full day ──
        {
            "message": "tuesday: chris tennis 6:30-8am, family fitness & pool at liberty athletic 10am "
            "(we have guest passes), lunch is choose your own adventure leftovers welcome, "
            "order joes pizza 3:30pm, joes pizza for dinner, leave for greenfield village 5:20pm, "
            "greenfield village 5:45-8pm",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 8,
            },
            "notes": "Dense Tuesday. Activities, meals, and implicit todo (order pizza). "
            "Liberty Athletic and Greenfield Village get map links. Joe's Pizza gets map link.",
        },
        # ── Turn 11: Christmas Eve ──
        {
            "message": "christmas eve: chris birthday tennis 8-10am, ana & fredy cleaning 12-2pm, "
            "smoked pork shoulder carnitas with all the fixings for party, "
            "chris's rocking xmas eve birthday party 3-8pm",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 4,
            },
            "notes": "Christmas Eve activities and party food. Cleaning marked done.",
        },
        # ── Turn 12: Christmas Eve todos ──
        {
            "message": "christmas eve party prep: chris smoke carnitas in morning, "
            "everybody house prep for party samantha is captain, "
            "chris lay out taco table accoutrements, "
            "chris and nicole devise signature cocktail punch feeds 15 adults",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 4,
            },
            "notes": "4 party prep tasks in eve_todos checklist.",
        },
        # ── Turn 13: Christmas Day ──
        {
            "message": "christmas day: presents in morning, christmas brunch, "
            "smoked prime rib supper at 3pm with mashed potatoes baked beans and popovers",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 6,
            },
            "notes": "Christmas Day activity (presents) and meals (brunch, prime rib supper with sides).",
        },
        # ── Turn 14: Christmas Day todos ──
        {
            "message": "christmas day todos: sam and chris f set breakfast table with toys, "
            "chris li make christmas brunch, chris li smoke prime rib",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 3,
            },
            "notes": "3 todos for Christmas Day in xmas_todos checklist.",
        },
        # ── Turn 15: Friday ──
        {
            "message": "friday: chris & nicole in midland all day, biwako for lunch, "
            "kids movie zootopia or spongebob with isla & esme, "
            "leftovers or basil babe for dinner depending on how we're feeling",
            "expected_tier": "L3",
            "checks": {
                "min_entities": 4,
            },
            "notes": "Friday activities and meals. Midland trip marked done with map link. "
            "Biwako gets map link. Dinner has note about mood-dependent choice.",
        },
    ],
}


# ---------------------------------------------------------------------------
# All complex scenarios
# ---------------------------------------------------------------------------

COMPLEX_SCENARIOS = [
    CHRISTMAS_WEEK_REALISTIC,
    CHRISTMAS_WEEK_IDEAL,
]
