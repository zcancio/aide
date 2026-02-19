"""
Tests for backend/services/jsonl_parser.py
"""

from __future__ import annotations

from backend.services.jsonl_parser import JSONLParser


class TestParseSingleLine:
    def test_basic_event(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"page"}\n')
        assert len(lines) == 1
        assert lines[0]["type"] == "entity.create"
        assert lines[0]["id"] == "page"

    def test_with_props_expanded_to_payload(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"p1","p":{"name":"Test"}}\n')
        assert len(lines) == 1
        assert lines[0]["type"] == "entity.create"
        assert lines[0]["payload"] == {"name": "Test"}

    def test_no_trailing_newline_returns_empty(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"p1"}')
        assert lines == []

    def test_empty_line_skipped(self):
        parser = JSONLParser()
        lines = parser.feed("\n")
        assert lines == []

    def test_whitespace_only_line_skipped(self):
        parser = JSONLParser()
        lines = parser.feed("   \n")
        assert lines == []


class TestPartialBuffer:
    def test_partial_then_complete(self):
        parser = JSONLParser()
        # First chunk is partial
        result1 = parser.feed('{"t":"ent')
        assert result1 == []
        # Second chunk completes the line
        result2 = parser.feed('ity.create","id":"page"}\n')
        assert len(result2) == 1
        assert result2[0]["type"] == "entity.create"

    def test_multiple_lines_in_one_chunk(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"a"}\n{"t":"entity.create","id":"b"}\n')
        assert len(lines) == 2
        assert lines[0]["id"] == "a"
        assert lines[1]["id"] == "b"

    def test_buffer_accumulates_across_feeds(self):
        parser = JSONLParser()
        parser.feed('{"t":')
        parser.feed('"entity')
        parser.feed('.create","id":"x"}')
        result = parser.feed("\n")
        assert len(result) == 1
        assert result[0]["type"] == "entity.create"


class TestMalformedLines:
    def test_skip_malformed_line(self):
        parser = JSONLParser()
        lines = parser.feed('not json\n{"t":"entity.create","id":"x"}\n')
        assert len(lines) == 1
        assert lines[0]["type"] == "entity.create"

    def test_skip_multiple_malformed_lines(self):
        parser = JSONLParser()
        lines = parser.feed('bad\nalso bad\n{"t":"entity.create","id":"y"}\n')
        assert len(lines) == 1

    def test_truncated_json_skipped_on_flush(self):
        parser = JSONLParser()
        parser.feed('{"t":"entity.create"')  # no newline, no closing brace
        flushed = parser.flush()
        assert flushed == []


class TestExpandAbbreviations:
    def test_t_expands_to_type(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create"}\n')
        assert "type" in lines[0]
        assert "t" not in lines[0]

    def test_p_expands_to_payload(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","p":{"name":"Alice"}}\n')
        assert "payload" in lines[0]
        assert "p" not in lines[0]
        assert lines[0]["payload"]["name"] == "Alice"

    def test_already_full_keys_unchanged(self):
        parser = JSONLParser()
        lines = parser.feed('{"type":"entity.create","payload":{"x":1}}\n')
        assert lines[0]["type"] == "entity.create"
        assert lines[0]["payload"] == {"x": 1}

    def test_id_field_preserved(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"my_entity"}\n')
        assert lines[0]["id"] == "my_entity"

    def test_parent_field_preserved(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"child","parent":"parent_id","p":{}}\n')
        assert lines[0]["parent"] == "parent_id"

    def test_display_field_preserved(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"entity.create","id":"x","display":"card","p":{}}\n')
        assert lines[0]["display"] == "card"

    def test_voice_event_expanded(self):
        parser = JSONLParser()
        lines = parser.feed('{"t":"voice","text":"Hello world"}\n')
        assert lines[0]["type"] == "voice"
        assert lines[0]["text"] == "Hello world"


class TestFlush:
    def test_flush_empty_buffer(self):
        parser = JSONLParser()
        result = parser.flush()
        assert result == []

    def test_flush_complete_line_without_newline(self):
        parser = JSONLParser()
        parser.feed('{"t":"entity.create","id":"x"}')
        result = parser.flush()
        assert len(result) == 1
        assert result[0]["type"] == "entity.create"

    def test_flush_clears_buffer(self):
        parser = JSONLParser()
        parser.feed('{"t":"entity.create","id":"x"}')
        parser.flush()
        # Buffer should be empty after flush
        result = parser.flush()
        assert result == []

    def test_flush_then_feed_fresh(self):
        parser = JSONLParser()
        parser.feed("partial")
        parser.flush()
        # After flush, buffer is cleared — new content starts fresh
        lines = parser.feed('{"t":"entity.create","id":"fresh"}\n')
        assert len(lines) == 1
