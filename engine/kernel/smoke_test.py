"""
End-to-end smoke test for AIde kernel.

Tests the full flow: events → reducer → renderer → HTML
"""

import asyncio

from engine.kernel.assembly import AideAssembly, MemoryStorage, parse_aide_html
from engine.kernel.reducer import empty_state, reduce
from engine.kernel.renderer import render
from engine.kernel.types import Blueprint, Event, RenderOptions


async def main():
    print("🧪 AIde Kernel End-to-End Smoke Test")
    print("=" * 60)

    # Step 1: Create events
    print("\n1️⃣  Creating primitive events...")
    events = [
        Event(
            id="evt_1",
            sequence=1,
            timestamp="2024-01-01T00:00:00Z",
            actor="test",
            source="smoke_test",
            type="meta.update",
            payload={"title": "Grocery List"},
        ),
        Event(
            id="evt_2",
            sequence=2,
            timestamp="2024-01-01T00:00:01Z",
            actor="test",
            source="smoke_test",
            type="collection.create",
            payload={
                "id": "groceries",
                "name": "Items",
                "schema": {
                    "name": "string",
                    "checked": "bool",
                },
                "primary_field": "name",
            },
        ),
        Event(
            id="evt_3",
            sequence=3,
            timestamp="2024-01-01T00:00:02Z",
            actor="test",
            source="smoke_test",
            type="entity.create",
            payload={
                "collection": "groceries",
                "id": "item_milk",
                "fields": {"name": "Milk", "checked": False},
            },
        ),
        Event(
            id="evt_4",
            sequence=4,
            timestamp="2024-01-01T00:00:03Z",
            actor="test",
            source="smoke_test",
            type="entity.create",
            payload={
                "collection": "groceries",
                "id": "item_eggs",
                "fields": {"name": "Eggs", "checked": False},
            },
        ),
        Event(
            id="evt_5",
            sequence=5,
            timestamp="2024-01-01T00:00:04Z",
            actor="test",
            source="smoke_test",
            type="view.create",
            payload={
                "id": "view_main",
                "source": "groceries",
                "type": "list",
            },
        ),
        Event(
            id="evt_6",
            sequence=6,
            timestamp="2024-01-01T00:00:05Z",
            actor="test",
            source="smoke_test",
            type="block.set",
            payload={
                "id": "block_header",
                "type": "heading",
                "content": "My Groceries",
            },
        ),
        Event(
            id="evt_7",
            sequence=7,
            timestamp="2024-01-01T00:00:06Z",
            actor="test",
            source="smoke_test",
            type="block.set",
            payload={
                "id": "block_list",
                "type": "collection_view",
                "view_id": "view_main",
            },
        ),
        Event(
            id="evt_8",
            sequence=8,
            timestamp="2024-01-01T00:00:07Z",
            actor="test",
            source="smoke_test",
            type="block.set",
            payload={
                "id": "block_root",
                "type": "root",
                "children": ["block_header"],
            },
        ),
        Event(
            id="evt_9",
            sequence=9,
            timestamp="2024-01-01T00:00:08Z",
            actor="test",
            source="smoke_test",
            type="block.set",
            payload={
                "id": "block_root",
                "type": "root",
                "children": ["block_header", "block_list"],
            },
        ),
    ]
    print(f"   ✓ Created {len(events)} events")

    # Step 2: Apply events through reducer
    print("\n2️⃣  Applying events through reducer...")
    snapshot = empty_state()
    applied_count = 0
    for event in events:
        result = reduce(snapshot, event)
        if result.applied:
            snapshot = result.snapshot
            applied_count += 1
        else:
            print(f"   ✗ Event {event.id} rejected: {result.error}")
    print(f"   ✓ Applied {applied_count}/{len(events)} events successfully")

    # Verify snapshot state
    assert "groceries" in snapshot["collections"], "Collection not created"
    assert "item_milk" in snapshot["collections"]["groceries"]["entities"], "Entity not created"
    assert snapshot["meta"]["title"] == "Grocery List", "Meta not set"
    print("   ✓ Snapshot state verified")

    # Step 3: Render to HTML
    print("\n3️⃣  Rendering snapshot to HTML...")
    blueprint = Blueprint(
        identity="Simple grocery list tracker",
        voice="State reflections only. No encouragement.",
        prompt="You are managing a grocery list.",
    )
    html = render(snapshot, blueprint, events, RenderOptions())
    print(f"   ✓ Generated HTML ({len(html)} bytes)")

    # Verify HTML structure
    assert "<!DOCTYPE html>" in html, "Missing DOCTYPE"
    assert '<html lang="en">' in html, "Missing HTML tag"
    assert "Grocery List" in html, "Missing title"
    assert "My Groceries" in html, "Missing heading"
    assert "Milk" in html, "Missing entity content"
    assert "Eggs" in html, "Missing entity content"
    print("   ✓ HTML structure verified")

    # Step 4: Parse HTML back
    print("\n4️⃣  Parsing HTML back to extract data...")
    parsed = parse_aide_html(html)
    assert parsed.snapshot is not None, "Snapshot not extracted"
    assert parsed.blueprint is not None, "Blueprint not extracted"
    assert len(parsed.events) == len(events), f"Events count mismatch: {len(parsed.events)} != {len(events)}"
    print("   ✓ Successfully parsed HTML")
    print(f"   ✓ Extracted {len(parsed.events)} events")

    # Step 5: Assembly layer round-trip
    print("\n5️⃣  Testing assembly layer round-trip...")
    storage = MemoryStorage()
    assembly = AideAssembly(storage)

    # Create new aide
    blueprint_new = Blueprint(
        identity="Grocery list for the week",
        voice="No first person. State reflections only.",
    )
    aide_file = await assembly.create(blueprint_new)
    aide_id = aide_file.aide_id
    print(f"   ✓ Created aide: {aide_id}")

    # Apply events
    result = await assembly.apply(aide_file, events)
    print(f"   ✓ Applied {len(result.applied)} events (rejected: {len(result.rejected)})")

    # Save
    await assembly.save(aide_file)
    print("   ✓ Saved to storage")

    # Load back
    loaded = await assembly.load(aide_id)
    assert loaded.aide_id == aide_id, "Aide ID mismatch"
    assert loaded.snapshot["meta"]["title"] == "Grocery List", "State not preserved"
    print("   ✓ Loaded from storage and verified")

    # Publish (pro tier - no footer)
    publish_url = await assembly.publish(loaded, slug="my-groceries", is_free_tier=False)
    assert publish_url is not None, "Publish failed"
    print(f"   ✓ Published to: {publish_url}")

    # Verify published HTML
    published_html = storage.published.get("my-groceries")
    assert published_html is not None, "Published HTML not found"
    assert "Made with AIde" not in published_html, "Pro tier should not have footer"
    print("   ✓ Published HTML verified (no footer for pro tier)")

    # Test free tier with footer
    publish_url_free = await assembly.publish(loaded, slug="my-groceries-free", is_free_tier=True)
    published_html_free = storage.published.get("my-groceries-free")
    assert "Made with AIde" in published_html_free, "Free tier should have footer"
    print("   ✓ Free tier footer verified")

    print("\n" + "=" * 60)
    print("✅ All smoke tests passed!")
    print("\nKernel is functioning correctly:")
    print("  • Events → Reducer → Snapshot ✓")
    print("  • Snapshot → Renderer → HTML ✓")
    print("  • HTML → Parser → Data ✓")
    print("  • Assembly layer (create/apply/save/load/publish) ✓")
    print("  • Round-trip integrity ✓")


if __name__ == "__main__":
    asyncio.run(main())
