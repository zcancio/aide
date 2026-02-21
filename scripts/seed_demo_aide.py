#!/usr/bin/env python3
"""
Seed a demo aide with all display types.

Usage:
    python scripts/seed_demo_aide.py [user_id]

If no user_id provided, uses the first user in the database.
Creates an aide called "Component Showcase" with examples of every display type.
"""

import asyncio
import sys
from datetime import UTC, datetime
from uuid import UUID, uuid4

# Add project root to path
sys.path.insert(0, ".")

from backend.db import init_pool, close_pool, user_conn, system_conn


DEMO_SNAPSHOT = {
    "version": 2,
    "entities": {
        # Page root
        "page": {
            "id": "page",
            "display": "page",
            "parent": None,
            "props": {
                "title": "Component Showcase",
                "subtitle": "A demo of all AIde display types"
            }
        },

        # Section: Metrics
        "metrics_section": {
            "id": "metrics_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Metrics"}
        },
        "metric_budget": {
            "id": "metric_budget",
            "display": "metric",
            "parent": "metrics_section",
            "props": {"label": "Budget", "value": "$12,500"}
        },
        "metric_spent": {
            "id": "metric_spent",
            "display": "metric",
            "parent": "metrics_section",
            "props": {"label": "Spent", "value": "$8,340"}
        },
        "metric_remaining": {
            "id": "metric_remaining",
            "display": "metric",
            "parent": "metrics_section",
            "props": {"label": "Remaining", "value": "$4,160"}
        },

        # Section: Text
        "text_section": {
            "id": "text_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Text Display"}
        },
        "text_intro": {
            "id": "text_intro",
            "display": "text",
            "parent": "text_section",
            "props": {
                "text": "This is a text display component. It renders paragraphs with proper typography and spacing. Use it for descriptions, notes, or any longer-form content."
            }
        },

        # Section: Cards
        "cards_section": {
            "id": "cards_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Card Display"}
        },
        "card_project": {
            "id": "card_project",
            "display": "card",
            "parent": "cards_section",
            "props": {
                "name": "Kitchen Renovation",
                "status": "In Progress",
                "start_date": "2024-01-15",
                "contractor": "BuildRight Co.",
                "budget": "$45,000"
            }
        },
        "card_contact": {
            "id": "card_contact",
            "display": "card",
            "parent": "cards_section",
            "props": {
                "name": "John Smith",
                "role": "Project Manager",
                "email": "john@example.com",
                "phone": "(555) 123-4567"
            }
        },

        # Section: Checklist
        "checklist_section": {
            "id": "checklist_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Checklist"}
        },
        "checklist_container": {
            "id": "checklist_container",
            "display": "checklist",
            "parent": "checklist_section",
            "props": {}
        },
        "task_1": {
            "id": "task_1",
            "parent": "checklist_container",
            "props": {"label": "Review project scope", "done": True}
        },
        "task_2": {
            "id": "task_2",
            "parent": "checklist_container",
            "props": {"label": "Get contractor quotes", "done": True}
        },
        "task_3": {
            "id": "task_3",
            "parent": "checklist_container",
            "props": {"label": "Finalize budget", "done": False}
        },
        "task_4": {
            "id": "task_4",
            "parent": "checklist_container",
            "props": {"label": "Schedule start date", "done": False}
        },

        # Section: Table
        "table_section": {
            "id": "table_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Table Display"}
        },
        "table_expenses": {
            "id": "table_expenses",
            "display": "table",
            "parent": "table_section",
            "props": {"title": "Recent Expenses"}
        },
        "expense_1": {
            "id": "expense_1",
            "parent": "table_expenses",
            "props": {
                "date": "2024-02-15",
                "category": "Materials",
                "description": "Lumber and framing",
                "amount": 2450
            }
        },
        "expense_2": {
            "id": "expense_2",
            "parent": "table_expenses",
            "props": {
                "date": "2024-02-18",
                "category": "Labor",
                "description": "Demolition crew",
                "amount": 1800
            }
        },
        "expense_3": {
            "id": "expense_3",
            "parent": "table_expenses",
            "props": {
                "date": "2024-02-20",
                "category": "Materials",
                "description": "Electrical supplies",
                "amount": 890
            }
        },
        "expense_4": {
            "id": "expense_4",
            "parent": "table_expenses",
            "props": {
                "date": "2024-02-22",
                "category": "Permits",
                "description": "Building permit",
                "amount": 350
            }
        },

        # Section: List
        "list_section": {
            "id": "list_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "List Display"}
        },
        "list_team": {
            "id": "list_team",
            "display": "list",
            "parent": "list_section",
            "props": {"title": "Team Members"}
        },
        "member_1": {
            "id": "member_1",
            "parent": "list_team",
            "props": {"name": "Alice Chen", "role": "Architect"}
        },
        "member_2": {
            "id": "member_2",
            "parent": "list_team",
            "props": {"name": "Bob Martinez", "role": "General Contractor"}
        },
        "member_3": {
            "id": "member_3",
            "parent": "list_team",
            "props": {"name": "Carol Williams", "role": "Electrician"}
        },
        "member_4": {
            "id": "member_4",
            "parent": "list_team",
            "props": {"name": "David Kim", "role": "Plumber"}
        },

        # Section: Image
        "image_section": {
            "id": "image_section",
            "display": "section",
            "parent": "page",
            "props": {"title": "Image Display"}
        },
        "image_placeholder": {
            "id": "image_placeholder",
            "display": "image",
            "parent": "image_section",
            "props": {
                "src": "https://placehold.co/600x300/f5f1eb/374151?text=Project+Photo",
                "alt": "Project progress photo",
                "caption": "Current state of the kitchen renovation"
            }
        },
    },
    "meta": {
        "title": "Component Showcase",
        "description": "A demo aide showcasing all available display types"
    },
    "root_ids": ["page"]
}


async def get_first_user() -> tuple[UUID, str] | None:
    """Get the first user in the database."""
    async with system_conn() as conn:
        row = await conn.fetchrow("SELECT id, email FROM users LIMIT 1")
        return (row["id"], row["email"]) if row else None


async def create_demo_aide(user_id: UUID) -> UUID:
    """Create the demo aide with all display types."""
    aide_id = uuid4()
    now = datetime.now(UTC)

    async with user_conn(user_id) as conn:
        await conn.execute(
            """
            INSERT INTO aides (id, user_id, title, state, r2_prefix, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $6)
            """,
            aide_id,
            user_id,
            "Component Showcase",
            DEMO_SNAPSHOT,
            f"aides/{aide_id}",
            now,
        )

    return aide_id


async def main():
    await init_pool()

    try:
        if len(sys.argv) >= 2:
            user_id = UUID(sys.argv[1])
            email = "(provided)"
        else:
            result = await get_first_user()
            if not result:
                print("No users in database")
                sys.exit(1)
            user_id, email = result
            print(f"Using user: {email}")

        aide_id = await create_demo_aide(user_id)
        print(f"Created demo aide: {aide_id}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
