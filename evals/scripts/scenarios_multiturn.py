"""
Multi-turn eval scenarios.

Real users don't front-load all context. They drip-feed over multiple messages,
often vague, sometimes contradicting themselves, sometimes asking questions
mid-build. These scenarios test the full conversational loop:

  Turn 1: L3 creates initial structure from vague input
  Turn 2: L2 updates with more detail
  Turn 3: L2 adds entities
  Turn 4: L4 answers a question
  Turn 5: L2 updates based on the answer
  ...

Each turn specifies:
  - message: what the user says (realistic, messy, human)
  - expected_tier: which tier should handle this
  - checks: what to validate on the output
  - notes: why this turn matters for eval purposes
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Graduation Party — realistic build over 12 turns
# ---------------------------------------------------------------------------

GRADUATION_REALISTIC = {
    "name": "graduation_realistic",
    "description": "User plans graduation party over multiple messages, starting vague and adding detail.",
    "turns": [
        # ── Turn 1: Vague kickoff ──
        {
            "message": "sophie's graduating in may, need to plan something",
            "expected_tier": "L3",
            "checks": {
                "creates_page": True,
                "has_meta": True,
                "not_over_scaffolded": True,  # should NOT create 5 sections from this
            },
            "notes": "Minimal input. L3 should create a basic page with maybe ceremony details as a card. "
                     "Should NOT pre-create guest list, food, todo — user hasn't mentioned any of that. "
                     "Title should mention Sophie/graduation, not be generic.",
        },
        # ── Turn 2: Adds basic details ──
        {
            "message": "ceremony is may 22 at UC Davis, starts at 10",
            "expected_tier": "L2",
            "checks": {
                "updates_existing": True,  # should update the ceremony/details entity
                "has_date": True,
                "has_venue": True,
            },
            "notes": "L2 should find the details entity and update it. Should NOT create a new entity. "
                     "Date should be '2026-05-22' or 'May 22'. Venue should be 'UC Davis'.",
        },
        # ── Turn 3: Guest info starts flowing ──
        {
            "message": "ok so aunt linda and uncle bob are definitely coming. cousin james is a maybe",
            "expected_tier": "L2",
            "checks": {
                "creates_guests": True,  # might need L3 if no guest section exists yet
            },
            "notes": "This is the interesting one. If Turn 1 didn't create a guest section, this should "
                     "escalate to L3 (new structure needed). If Turn 1 did create one, L2 handles it. "
                     "Either way: 3 entities with names, linda/bob = confirmed, james = maybe/pending. "
                     "Accept either L2 or L3 — both are correct depending on Turn 1's output.",
            "accept_tiers": ["L2", "L3"],
        },
        # ── Turn 4: More guests, casual style ──
        {
            "message": "also the garcias - maria and carlos. and prob my friend dave",
            "expected_tier": "L2",
            "checks": {
                "creates_3_guests": True,
                "names_correct": ["maria", "carlos", "dave"],
            },
            "notes": "L2 adds 3 more guests. 'prob' for dave means status should be pending/maybe. "
                     "Garcias are likely confirmed (no hedge word). Tests casual name resolution.",
        },
        # ── Turn 5: Question mid-build ──
        {
            "message": "how many people is that so far?",
            "expected_tier": "L4",
            "checks": {
                "answers_count": True,
                "plain_text": True,
                "no_mutations": True,
            },
            "notes": "L4 should count guests in the snapshot and respond with a number. "
                     "Should be 6 guests (linda, bob, james, maria, carlos, dave) plus Sophie = ~7. "
                     "Acceptable to count just the guest entities or include hosts. "
                     "Must NOT emit any JSONL or mutations.",
        },
        # ── Turn 6: Food section kicks off ──
        {
            "message": "we should do potluck. linda's bringing potato salad already",
            "expected_tier": "L3",
            "checks": {
                "creates_food_section": True,
                "potato_salad_entity": True,
                "linked_to_linda": True,  # bonus: relationship or assigned field
            },
            "notes": "New structural element (food section) → L3. Should create a food section "
                     "and at least one entity for potato salad. Bonus if it links to Linda via "
                     "an assigned/bringing field or relationship.",
            "accept_tiers": ["L2", "L3"],
        },
        # ── Turn 7: Batch of food items ──
        {
            "message": "carlos said he'll do carne asada, maria's handling drinks. we still need dessert and sides",
            "expected_tier": "L2",
            "checks": {
                "creates_food_items": True,
                "unassigned_items": True,  # dessert and sides should be TBD/unassigned
            },
            "notes": "L2 creates food entities. Carne asada assigned to Carlos, drinks to Maria. "
                     "Dessert and sides should exist but be unassigned/TBD. Tests mixed assigned + unassigned.",
        },
        # ── Turn 8: Contradiction/correction ──
        {
            "message": "actually scratch that - maria's doing a fruit platter, not drinks. bob said he'll handle drinks",
            "expected_tier": "L2",
            "checks": {
                "updates_maria": True,  # maria's food item changes
                "updates_bob_or_drinks": True,  # drinks reassigned to bob
            },
            "notes": "Tests correction handling. L2 should update Maria's assignment from drinks to "
                     "fruit platter, and assign drinks to Bob. Should NOT delete and recreate — should update.",
        },
        # ── Turn 9: Todo list ──
        {
            "message": "things we still gotta do: book the park pavilion, order a cake, get decorations, figure out parking",
            "expected_tier": "L3",
            "checks": {
                "creates_todo_section": True,
                "creates_4_tasks": True,
                "tasks_unchecked": True,
            },
            "notes": "New section (todo/checklist) → L3 or L2 if todo section exists. Should create "
                     "a checklist with 4 items, all unchecked. Display should be checklist, not table.",
            "accept_tiers": ["L2", "L3"],
        },
        # ── Turn 10: Quick update ──
        {
            "message": "booked the pavilion!",
            "expected_tier": "L2",
            "checks": {
                "marks_task_done": True,
                "compact": True,  # should be 1-2 lines max
            },
            "notes": "Classic L2 — find the 'book pavilion' task, set done=true. "
                     "Should be 1 line of JSONL + maybe a voice line. Tests entity resolution "
                     "('the pavilion' → 'book the park pavilion' task).",
        },
        # ── Turn 11: Query about readiness ──
        {
            "message": "what do we still need to figure out",
            "expected_tier": "L4",
            "checks": {
                "mentions_unchecked_todos": True,
                "mentions_unassigned_food": True,
                "plain_text": True,
            },
            "notes": "L4 should reason across the snapshot: unchecked todos (cake, decorations, parking), "
                     "unassigned food items (dessert, sides), maybe pending guests (james, dave). "
                     "Good L4 output connects the dots rather than listing raw data.",
        },
        # ── Turn 12: Guest update with travel info ──
        {
            "message": "james confirmed! he's flying in from chicago. and dave can't make it after all",
            "expected_tier": "L2",
            "checks": {
                "updates_james_confirmed": True,
                "updates_james_travel": True,
                "updates_dave_declined": True,
            },
            "notes": "Two guest updates in one message. James: confirmed + traveling_from=Chicago. "
                     "Dave: status=declined or removed. Tests multi-entity update from natural language.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Poker League — builds over 8 turns
# ---------------------------------------------------------------------------

POKER_REALISTIC = {
    "name": "poker_realistic",
    "description": "User sets up poker league incrementally, names arrive in batches.",
    "turns": [
        {
            "message": "starting a poker night with some guys",
            "expected_tier": "L3",
            "checks": {"creates_page": True, "has_meta": True},
            "notes": "Vague. Should create minimal page. Should NOT create 8 player slots.",
        },
        {
            "message": "it's gonna be me, mike, dave and tom to start",
            "expected_tier": "L2",
            "checks": {"creates_4_players": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Adds first batch of players. If no roster exists, may escalate to L3.",
        },
        {
            "message": "every other thursday, $20 buy in",
            "expected_tier": "L2",
            "checks": {"updates_details": True},
            "notes": "Adds schedule + buy-in to existing details.",
        },
        {
            "message": "sarah and jake want in too",
            "expected_tier": "L2",
            "checks": {"creates_2_players": True},
            "notes": "Adds 2 more players to existing roster.",
        },
        {
            "message": "we should track wins and who's hosting. first game was at mike's last thursday",
            "expected_tier": "L3",
            "checks": {"adds_schedule_or_fields": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "May need L3 for new fields (wins, hosting) or schedule section. "
                     "Should create a game/schedule entry for the first game.",
        },
        {
            "message": "mike won, $120 pot. tom ended up hosting",
            "expected_tier": "L2",
            "checks": {"updates_game_result": True, "updates_mike_wins": True},
            "notes": "Post-game update on the existing game. Should UPDATE game entity, not create new one.",
        },
        {
            "message": "who's won the most so far",
            "expected_tier": "L4",
            "checks": {"answers_standings": True, "plain_text": True},
            "notes": "L4 query over standings. After 1 game, Mike leads.",
        },
        {
            "message": "next game is at dave's place. also jake can't make it, lisa's subbing",
            "expected_tier": "L2",
            "checks": {"creates_game": True, "updates_jake": True, "creates_lisa": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Multi-intent: schedule next game + roster change (sub). "
                     "Tests whether L2 handles the sub correctly.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Grocery List — rapid-fire simple updates
# ---------------------------------------------------------------------------

GROCERY_REALISTIC = {
    "name": "grocery_realistic",
    "description": "Quick grocery list build, typical phone-speed messages. "
                   "Tests data preservation, corrections, grouping, and state reversal.",
    "turns": [
        {
            "message": "grocery run",
            "expected_tier": "L3",
            "checks": {"creates_page": True},
            "notes": "Two words. L3 should create a minimal grocery list page.",
        },
        {
            "message": "milk eggs bread",
            "expected_tier": "L2",
            "checks": {"creates_3_items": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "No punctuation, no 'add'. Just items. Should create 3 checklist items.",
        },
        {
            "message": "oh and butter. the good kind from trader joes",
            "expected_tier": "L2",
            "checks": {"creates_butter": True, "has_store_note": True},
            "notes": "Adds butter with a store/note qualifier. Tests whether 'trader joes' "
                     "gets captured as a field or note.",
        },
        {
            "message": "got the milk and eggs",
            "expected_tier": "L2",
            "checks": {"checks_off_2": True},
            "notes": "'got' = done. Should check off milk and eggs. Classic L2.",
        },
        {
            "message": "what's left",
            "expected_tier": "L4",
            "checks": {"lists_remaining": True, "plain_text": True},
            "notes": "L4 should filter unchecked items and list them.",
        },
        {
            "message": "add chicken thighs, rice, soy sauce, ginger, and green onions for tonight",
            "expected_tier": "L2",
            "checks": {"creates_5_items": True,
                       "expect_in_output": ["tonight"]},
            "notes": "Batch add 5 items. 'For tonight' is meaningful context — should appear "
                     "as a note, group label, or prop on the items. Dropping temporal context "
                     "loses user intent.",
        },
        {
            "message": "actually I already have rice at home",
            "expected_tier": "L2",
            "checks": {"marks_done_or_removes": True},
            "notes": "'Already have at home' = don't need to buy. Should mark rice done or "
                     "remove it. Either is acceptable — the key is the item leaves the "
                     "'remaining' list.",
        },
        {
            "message": "the chicken should be 2 lbs, bone-in",
            "expected_tier": "L2",
            "checks": {"updates_chicken": True,
                       "expect_in_output": ["2", "bone"]},
            "notes": "Adds quantity detail to existing chicken item. Should entity.update "
                     "chore_chicken_thighs with quantity or note. '2 lbs' and 'bone-in' "
                     "must appear in the output.",
        },
        {
            "message": "group the dinner stuff separately from the basics",
            "expected_tier": "L3",
            "checks": {"creates_sections": True},
            "notes": "Restructuring — needs L3 to create section entities and move items. "
                     "Should create something like a 'Dinner' section and a 'Basics' section "
                     "or similar grouping. Tests entity.move or re-parenting.",
        },
        {
            "message": "wait I didn't actually get the eggs yet",
            "expected_tier": "L2",
            "checks": {"unchecks_eggs": True},
            "notes": "Correction — reverses turn 4's check-off. Should set eggs done=false. "
                     "Tests that the model can undo previous state, not just advance it.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Home Renovation — longer build, mixed media
# ---------------------------------------------------------------------------

RENOVATION_REALISTIC = {
    "name": "renovation_realistic",
    "description": "Kitchen renovation tracking with budget, contractors, and timeline. "
                   "Tests budget line items vs tasks distinction, vendor switching, "
                   "timeline cascades, scope creep, and cross-entity queries.",
    "turns": [
        {
            "message": "redoing our kitchen, gonna be a project",
            "expected_tier": "L3",
            "checks": {"creates_page": True},
            "notes": "Vague kickoff. Minimal page creation.",
        },
        {
            "message": "budget is around 35k. already spent 8k on the architect plans",
            "expected_tier": "L3",
            "checks": {"creates_budget_table": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Should create a budget/line_items table with architect plans as the "
                     "first row (cost: 8000, done/committed). Architect plans are an EXPENSE "
                     "line item, not a task. Also set budget total on overview card. "
                     "L2 acceptable — will escalate when it needs to create a new section.",
        },
        {
            "message": "got 3 quotes for the cabinets: woodworks unlimited 12k, cabinet depot 9500, custom craft 15k",
            "expected_tier": "L3",
            "checks": {"creates_quote_table": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Structural: needs a parent table (cabinet_quotes or similar) with 3 row "
                     "children. Three sibling entities of the same type should be grouped under "
                     "a table, not dumped flat under page. L2 acceptable — will escalate for "
                     "new section creation.",
        },
        {
            "message": "going with cabinet depot",
            "expected_tier": "L2",
            "checks": {"uses_rel_for_selection": True},
            "notes": "Should select cabinet depot via rel.set (one_to_one 'selected' from "
                     "the quotes table or page to the quote entity), not a string prop like "
                     "'cabinet_vendor'. Selection among options is a relationship — switching "
                     "later is a single rel.set.",
        },
        {
            "message": "how much budget do we have left",
            "expected_tier": "L4",
            "checks": {"calculates_remaining": True, "plain_text": True},
            "notes": "L4 should sum committed costs from budget line items (architect 8k + "
                     "cabinets 9.5k = 17.5k) and subtract from 35k = 17.5k remaining.",
        },
        {
            "message": "plumber can start march 10, electrician march 3. need to get countertops measured before either",
            "expected_tier": "L3",
            "checks": {"creates_tasks": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Creates a TASKS section (checklist or table) with action items: "
                     "measure countertops, plumber, electrician. These are things to DO, "
                     "not expense line items. Tasks have dates and dependencies, "
                     "not costs.",
        },
        {
            "message": "cabinet depot called, price is actually 11k not 9500",
            "expected_tier": "L2",
            "checks": {"updates_existing": True,
                       "expect_in_output": ["11000|11k"]},
            "notes": "Price correction on existing quote. Must entity.update the cabinet depot "
                     "quote — NOT create a new one. The old price (9500) doesn't need to "
                     "appear in output — only the corrected value matters.",
        },
        {
            "message": "screw it, switching to woodworks. they'll honor the 9500 price",
            "expected_tier": "L2",
            "checks": {"uses_rel_for_selection": True,
                       "expect_in_output": ["woodworks", "9500"]},
            "notes": "Vendor switch via rel.set (one_to_one — auto-drops cabinet depot). "
                     "Also should entity.update woodworks quote price from 12k to 9500. "
                     "Tests rel.set + correlated entity.update in one turn.",
        },
        {
            "message": "also need new flooring, probably 4 to 6k. and appliances around 8k",
            "expected_tier": "L2",
            "checks": {"adds_budget_items": True, "budget_ceiling_intact": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Scope creep — adds 2 new BUDGET LINE ITEMS (not tasks). Flooring and "
                     "appliances are expenses with cost estimates. They belong in the budget "
                     "table alongside architect plans, not in the tasks section. "
                     "Budget total should NOT increase — 35k is the ceiling.",
        },
        {
            "message": "electrician pushed to march 17. plumber has to move too since they need electrical done first",
            "expected_tier": "L2",
            "checks": {"updates_dates": True,
                       "expect_in_output": ["17"]},
            "notes": "Timeline cascade. Electrician date changes from march 3 to march 17. "
                     "Plumber was march 10 but depends on electrical → must move AFTER march 17. "
                     "Both task entities need date updates. Tests dependency reasoning.",
        },
        {
            "message": "what's the full breakdown looking like",
            "expected_tier": "L4",
            "checks": {"comprehensive_summary": True, "plain_text": True},
            "notes": "L4 comprehensive query. Should list: budget ($35k), committed costs "
                     "(architect $8k, cabinets $9.5k with Woodworks), estimated costs "
                     "(flooring $4-6k, appliances $8k), remaining budget, timeline with "
                     "updated dates, and pending tasks. Tests cross-entity synthesis.",
        },
        {
            "message": "countertops are done, ended up costing 3200",
            "expected_tier": "L2",
            "checks": {"creates_budget_item": True,
                       "marks_prereq_done": True,
                       "expect_in_output": ["3200"]},
            "accept_tiers": ["L2", "L3"],
            "notes": "Creates a new countertops LINE ITEM in the budget table (cost: 3200, "
                     "done/paid). Also should mark task_measure_countertops as done — if "
                     "countertops are installed and paid for, the measurement prerequisite "
                     "is necessarily complete. Leaving it unchecked looks wrong.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Roommate Chores — tests clarify signal on ambiguous references
# ---------------------------------------------------------------------------

CHORES_CLARIFY = {
    "name": "chores_clarify",
    "description": "Roommate chore tracker that builds enough state to create genuine ambiguity. "
                   "Tests whether the model asks for clarification vs guessing.",
    "turns": [
        {
            "message": "roommate chore tracker for me, alex, and jamie",
            "expected_tier": "L3",
            "checks": {"creates_page": True, "creates_roster": True},
            "notes": "Straightforward setup. Should create page + 3 roommates.",
        },
        {
            "message": "weekly chores: dishes, vacuuming, bathroom cleaning, trash, mopping",
            "expected_tier": "L3",
            "checks": {"creates_5_chores": True},
            "accept_tiers": ["L2", "L3"],
            "notes": "Creates 5 chore entities. May need L3 for new section.",
        },
        {
            "message": "I'll do dishes and mopping. alex has vacuuming and trash. jamie does bathroom",
            "expected_tier": "L2",
            "checks": {"assigns_all": True},
            "notes": "Clear 1:1 assignments. No ambiguity. Should NOT clarify.",
        },
        {
            "message": "alex finished the vacuuming",
            "expected_tier": "L2",
            "checks": {"marks_done": True},
            "notes": "Single match — one vacuuming entity. Should NOT clarify. Just mark done.",
        },
        {
            "message": "swap mine and jamie's",
            "expected_tier": "L2",
            "checks": {"should_clarify": True},
            "notes": "SHOULD CLARIFY. 'Mine' = dishes + mopping (two chores). Jamie's = bathroom (one). "
                     "Swap which of my two? Both? Model can't know — must ask.",
        },
        {
            "message": "add a new chore - wipe down kitchen counters. jamie can do it",
            "expected_tier": "L2",
            "checks": {"creates_chore": True, "assigns_jamie": True},
            "notes": "Clear intent, clear assignment. Should NOT clarify.",
        },
        {
            "message": "mark jamie's as done",
            "expected_tier": "L2",
            "checks": {"should_clarify": True},
            "notes": "SHOULD CLARIFY. Jamie now has bathroom + kitchen counters (maybe dishes/mopping "
                     "too if swap happened). Which one is done? Model must ask.",
        },
        {
            "message": "kitchen counters",
            "expected_tier": "L2",
            "checks": {"resolves_clarify": True, "marks_done": True},
            "notes": "Answers the clarify from turn 7. Should mark chore_kitchen_counters done=true. "
                     "Short answer — model must understand this resolves the previous question, "
                     "not create a new entity or ask again.",
        },
        {
            "message": "actually remove one of alex's chores",
            "expected_tier": "L2",
            "checks": {"should_clarify": True},
            "notes": "SHOULD CLARIFY. Alex has vacuuming (done) + trash. Remove which? "
                     "Probably the done one, but model shouldn't assume.",
        },
        {
            "message": "the vacuuming since it's already done",
            "expected_tier": "L2",
            "checks": {"resolves_clarify": True, "unassigns_chore": True},
            "notes": "Answers the clarify from turn 9. Should rel.remove the assigned_to "
                     "relationship between chore_vacuuming and member_alex — NOT entity.remove "
                     "the chore itself. 'Remove one of alex's chores' means take it off alex's "
                     "plate, not delete vacuuming from the tracker. The chore entity stays.",
        },
    ],
}


# ---------------------------------------------------------------------------
# Flu Tracker — tests time-series data (readings as append-only rows)
# ---------------------------------------------------------------------------

FLU_TRACKER = {
    "name": "flu_tracker",
    "description": "Family flu temperature tracker with real-world data density. Tests "
                   "time-series append pattern (each reading is a NEW entity), batch data "
                   "entry, terse time/temp parsing, inline meds and notes, multi-person "
                   "multi-day state, and data-dense L4 synthesis.",
    "turns": [
        # ── Setup ──
        {
            "message": "kids are sick, need to track fevers for ringo and george",
            "expected_tier": "L3",
            "checks": {"creates_page": True},
            "notes": "Setup. Should create page with per-person sections or a readings "
                     "table. Structure must support MANY readings per person per day. "
                     "Don't over-scaffold — just the container.",
        },
        # ── Sunday Dec 29: Ringo's first day ──
        {
            "message": "ringo sunday dec 29: 1030am 103.7 tylenol, 135pm 101.5 motrin, 520pm 101 tylenol, 820pm 102 motrin",
            "expected_tier": "L2",
            "checks": {"batch_creates": True, "min_entities": 4,
                       "expect_in_output": ["103.7", "101.5", "101", "102"]},
            "accept_tiers": ["L2", "L3"],
            "notes": "Batch entry — 4 readings in one message. Each reading must be a "
                     "SEPARATE entity. '1030am' = 10:30 AM, '135pm' = 1:35 PM, etc. "
                     "Each has a med (alternating tylenol/motrin). Tests terse batch parsing.",
        },
        # ── Summary cards request ──
        {
            "message": "create a summary card for each kid",
            "expected_tier": "L3",
            "checks": {"creates_2_cards": True},
            "notes": "User wants per-kid summary cards before more data comes in. Should "
                     "create 2 card entities (one for Ringo, one for George) that can hold "
                     "summary stats like latest temp, last med, trend. Tests structural "
                     "creation mid-build. Cards should be distinct from the readings table.",
        },
        # ── Monday Dec 30: Ringo's long day ──
        {
            "message": "ringo monday: 12am 101.6 tylenol - woke him back to sleep. "
                     "2am 103.5 motrin - down to 101 by 245. "
                     "630am 98.6 no meds. "
                     "925am 99.8 tylenol. "
                     "1030am 100.3 no meds. "
                     "115pm 101.1 motrin. "
                     "2pm 101.4 no meds",
            "expected_tier": "L2",
            "checks": {"batch_creates": True, "min_entities": 7,
                       "captures_note": True,
                       "expect_in_output": ["103.5", "98.6", "101.1"]},
            "accept_tiers": ["L2", "L3"],
            "notes": "7 readings in one message. Massive batch. Inline notes on two readings "
                     "('woke him back to sleep', 'down to 101 by 245'). Each MUST be a "
                     "separate entity. Tests high-volume append pattern. The 98.6 is notable — "
                     "fever broke then came back.",
        },
        # ── Monday Dec 30: George's long day ──
        {
            "message": "george monday: 2am 102.7 tylenol. "
                     "630am 102.7 tylenol. "
                     "925am 101 no meds. "
                     "1030am 102.9 motrin - 1130 eye lids swelling. "
                     "115pm 100.3 no meds. "
                     "2pm 101.3 tylenol - threw up. "
                     "3pm 101.9 no meds. "
                     "4pm 103 motrin",
            "expected_tier": "L2",
            "checks": {"batch_creates": True, "min_entities": 8,
                       "captures_note": True,
                       "expect_in_output": ["102.7", "102.9", "103"]},
            "accept_tiers": ["L2", "L3"],
            "notes": "8 readings for george. Critical notes: 'eye lids swelling' (symptom "
                     "escalation at 11:30, separate from 10:30 reading time), 'threw up' "
                     "(on 2pm reading). Tests that notes attach to correct readings. "
                     "The 102.7 → 102.7 (no improvement after tylenol) is significant.",
        },
        # ── Status check after big data dump ──
        {
            "message": "how are they doing? who's worse?",
            "expected_tier": "L4",
            "checks": {"trend_summary": True, "plain_text": True},
            "notes": "L4 must synthesize across 2 kids, 2 days, ~19 readings total. "
                     "George is worse: higher peaks (103), not responding to tylenol "
                     "(102.7→102.7), vomiting, eye swelling. Ringo had a bad spike "
                     "(103.7, 103.5) but responded to meds. Should identify George as "
                     "more concerning.",
        },
        # ── Tuesday Dec 31: New day entries ──
        {
            "message": "ringo tues 5pm 101 tylenol, 830pm 99.7 motrin",
            "expected_tier": "L2",
            "checks": {"appends_not_updates": True,
                       "expect_in_output": ["101", "99.7"]},
            "notes": "New day, 2 more ringo readings. Must be NEW entities (not updates "
                     "to monday readings). Running total: ringo now has 13 readings across "
                     "3 days.",
        },
        {
            "message": "george tues 740pm 100.5 tylenol",
            "expected_tier": "L2",
            "checks": {"appends_not_updates": True,
                       "expect_in_output": ["100.5"]},
            "notes": "Single george reading, new day. Must be NEW entity. George now has "
                     "9 readings across 2 days.",
        },
        # ── Pattern question ──
        {
            "message": "is the tylenol even working for george? feels like it doesn't do anything",
            "expected_tier": "L4",
            "checks": {"george_med_analysis": True, "plain_text": True},
            "notes": "L4 should look at george's post-tylenol readings. Monday 2am tylenol → "
                     "630am still 102.7 (no drop). 2pm tylenol → 3pm 101.9 (marginal). "
                     "Motrin readings show more improvement. Should compare tylenol vs motrin "
                     "effectiveness for george specifically.",
        },
        # ── Retroactive correction ──
        {
            "message": "wait the 925am one for george on monday was actually 101.5 not 101",
            "expected_tier": "L2",
            "checks": {"updates_existing": True,
                       "expect_in_output": ["101.5"]},
            "notes": "Correction to existing reading. This IS an entity.update (not a new "
                     "reading). The user is fixing a data entry error, not logging a new check. "
                     "Must find the right george reading (monday 9:25am) and update the temp.",
        },
        # ── When to worry ──
        {
            "message": "what's george's highest temp been? should we go to the ER?",
            "expected_tier": "L4",
            "checks": {"george_peak": True, "plain_text": True},
            "notes": "L4 should find george's peak: 103°F on monday 4pm. Should also note "
                     "concerning symptoms (eye swelling, vomiting) alongside the fever data. "
                     "Should NOT give medical advice but can note what the data shows.",
        },
    ],
}


# ---------------------------------------------------------------------------
# All multi-turn scenarios
# ---------------------------------------------------------------------------

MULTI_TURN_SCENARIOS = [
    GRADUATION_REALISTIC,
    POKER_REALISTIC,
    GROCERY_REALISTIC,
    RENOVATION_REALISTIC,
    CHORES_CLARIFY,
    FLU_TRACKER,
]

# ---------------------------------------------------------------------------
# Scenario metadata for eval harness
# ---------------------------------------------------------------------------

def get_scenario_names() -> list[str]:
    return [s["name"] for s in MULTI_TURN_SCENARIOS]


def get_scenario(name: str) -> dict | None:
    return next((s for s in MULTI_TURN_SCENARIOS if s["name"] == name), None)
