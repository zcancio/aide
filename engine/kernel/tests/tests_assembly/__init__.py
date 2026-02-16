"""
AIde Assembly Test Suite

Tests for the assembly layer, organized by categories from aide_assembly_spec.md.

Test Files:
1. test_assembly_round_trip.py - Create → apply → save → load
2. test_assembly_parse_assemble.py - Parse ↔ assemble HTML
3. test_assembly_apply_rejections.py - Partial application with rejections
4. test_assembly_create_empty.py - Create empty aide validation
5. test_assembly_fork.py - Fork preserves snapshot, clears events
6. test_assembly_publish.py - Publish with/without footer
7. test_assembly_compaction.py - Event log compaction
8. test_assembly_integrity.py - Integrity check and repair
9. test_assembly_concurrency.py - Concurrent applies and locking
10. test_assembly_new_aide_flow.py - Complete first message flow
"""
