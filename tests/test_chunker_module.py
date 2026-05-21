"""Unit tests for the chunker.py module."""

from __future__ import annotations

import pytest

from utils.chunker import _format_snippet, chunk_nodes


class TestFormatSnippet:
    def test_format_dict_with_name(self):
        # 1. Dict with name and source
        node = {"name": "foo", "source": "def foo():\n    pass"}
        assert _format_snippet(node) == "=== foo ===\ndef foo():\n    pass"

    def test_format_dict_with_label(self):
        # 2. Dict with label and source
        node = {"label": "bar", "source": "def bar():\n    pass"}
        assert _format_snippet(node) == "=== bar ===\ndef bar():\n    pass"

    def test_format_dict_with_both_prefer_name(self):
        # 3. Prefer name if both name and label are present
        node = {"name": "foo", "label": "bar", "source": "def foo():\n    pass"}
        assert _format_snippet(node) == "=== foo ===\ndef foo():\n    pass"

    def test_format_dict_no_name_uses_unknown(self):
        # 4. Use <unknown> if name/label are missing
        node = {"source": "def baz():\n    pass"}
        assert _format_snippet(node) == "=== <unknown> ===\ndef baz():\n    pass"

    def test_format_dict_empty_source(self):
        # 5. Returns empty string if source is blank/whitespace
        assert _format_snippet({"name": "foo", "source": ""}) == ""
        assert _format_snippet({"name": "foo", "source": "   \n  "}) == ""
        assert _format_snippet({"name": "foo"}) == ""

    def test_format_non_dict(self):
        # 6. Returns str(node) if node is not a dict
        assert _format_snippet("raw string snippet") == "raw string snippet"
        assert _format_snippet(42) == "42"


class TestEdgeCases:
    def test_empty_list(self):
        # 7. Empty list input returns []
        assert chunk_nodes([]) == []

    def test_all_blank_nodes(self):
        # 8. All blank nodes input returns []
        nodes = [
            {"name": "foo", "source": ""},
            {"name": "bar", "source": "   "},
            "",
            "   "
        ]
        assert chunk_nodes(nodes) == []

    def test_single_node(self):
        # 9. Single node returns single chunk
        node = {"name": "foo", "source": "def f(): pass"}
        res = chunk_nodes([node])
        assert res == ["=== foo ===\ndef f(): pass"]

    def test_huge_node_emitted(self):
        # 10. Single node larger than max_chars is still emitted
        huge_source = "x = " + ("a" * 4000)
        node = {"name": "huge", "source": huge_source}
        res = chunk_nodes([node], max_chars=3000)
        assert len(res) == 1
        assert res[0] == f"=== huge ===\n{huge_source}"

    def test_return_type(self):
        # 11. Return type is a list of strings
        res = chunk_nodes([{"name": "foo", "source": "pass"}])
        assert isinstance(res, list)
        assert all(isinstance(x, str) for x in res)


class TestItemLimit:
    def test_three_to_one(self):
        # 12. 3 small items fit in 1 chunk
        nodes = [
            {"name": "n1", "source": "s1"},
            {"name": "n2", "source": "s2"},
            {"name": "n3", "source": "s3"},
        ]
        res = chunk_nodes(nodes, max_items=3)
        assert len(res) == 1
        assert "n1" in res[0] and "n2" in res[0] and "n3" in res[0]

    def test_four_to_two(self):
        # 13. 4 small items split into 2 chunks (3 and 1)
        nodes = [
            {"name": "n1", "source": "s1"},
            {"name": "n2", "source": "s2"},
            {"name": "n3", "source": "s3"},
            {"name": "n4", "source": "s4"},
        ]
        res = chunk_nodes(nodes, max_items=3)
        assert len(res) == 2
        assert len(res[0].split("\n\n")) == 3
        assert len(res[1].split("\n\n")) == 1

    def test_six_to_two(self):
        # 14. 6 small items split into 2 chunks (3 and 3)
        nodes = [{"name": f"n{i}", "source": f"s{i}"} for i in range(1, 7)]
        res = chunk_nodes(nodes, max_items=3)
        assert len(res) == 2
        assert len(res[0].split("\n\n")) == 3
        assert len(res[1].split("\n\n")) == 3

    def test_seven_to_three(self):
        # 15. 7 small items split into 3 chunks (3, 3, 1)
        nodes = [{"name": f"n{i}", "source": f"s{i}"} for i in range(1, 8)]
        res = chunk_nodes(nodes, max_items=3)
        assert len(res) == 3
        assert len(res[0].split("\n\n")) == 3
        assert len(res[1].split("\n\n")) == 3
        assert len(res[2].split("\n\n")) == 1

    def test_custom_max_items_one(self):
        # 16. Custom max_items=1 forces split on every node
        nodes = [{"name": f"n{i}", "source": f"s{i}"} for i in range(1, 4)]
        res = chunk_nodes(nodes, max_items=1)
        assert len(res) == 3

    def test_custom_max_items_five(self):
        # 17. Custom max_items=5 packs up to 5 items
        nodes = [{"name": f"n{i}", "source": f"s{i}"} for i in range(1, 6)]
        res = chunk_nodes(nodes, max_items=5)
        assert len(res) == 1
        assert len(res[0].split("\n\n")) == 5


class TestCharLimit:
    def test_two_long_nodes_split(self):
        # 18. Two long nodes that combined exceed max_chars split
        nodes = [
            {"name": "n1", "source": "a" * 1400},
            {"name": "n2", "source": "b" * 1500},
        ]
        # Max chars is 2800. Header characters and separator make it exceed.
        res = chunk_nodes(nodes, max_chars=2800)
        assert len(res) == 2

    def test_small_fit(self):
        # 19. Nodes that fit within max_chars stay in one chunk
        nodes = [
            {"name": "n1", "source": "a" * 100},
            {"name": "n2", "source": "b" * 100},
        ]
        res = chunk_nodes(nodes, max_chars=500)
        assert len(res) == 1

    def test_boundary(self):
        # 20. Exactly at the character count boundary splits correctly
        # Snip 1 len = === n1 ===\n + 10 chars = 11 + 10 = 21 chars
        # Snip 2 len = === n2 ===\n + 10 chars = 11 + 10 = 21 chars
        # Separator = 2 chars
        # Total combined = 44 chars.
        nodes = [
            {"name": "n1", "source": "a" * 10},
            {"name": "n2", "source": "b" * 10},
        ]
        assert len(chunk_nodes(nodes, max_chars=43)) == 2
        assert len(chunk_nodes(nodes, max_chars=44)) == 1

    def test_custom_max_chars(self):
        # 21. Custom max_chars parameter is respected
        nodes = [
            {"name": "n1", "source": "a" * 50},
            {"name": "n2", "source": "b" * 50},
        ]
        res = chunk_nodes(nodes, max_chars=80)
        assert len(res) == 2


class TestContent:
    def test_all_names_present(self):
        # 22. All item names are present in the output
        nodes = [{"name": f"target_name_{i}", "source": "pass"} for i in range(4)]
        res = chunk_nodes(nodes)
        combined_output = "".join(res)
        for i in range(4):
            assert f"target_name_{i}" in combined_output

    def test_newline_separator(self):
        # 23. Newline separator \n\n is present between snippets
        nodes = [
            {"name": "n1", "source": "pass"},
            {"name": "n2", "source": "pass"},
        ]
        res = chunk_nodes(nodes)
        assert len(res) == 1
        assert "\n\n" in res[0]

    def test_header_in_output(self):
        # 24. Exact header format is present in the output
        nodes = [{"name": "my_func", "source": "pass"}]
        res = chunk_nodes(nodes)
        assert "=== my_func ===" in res[0]

    def test_no_duplicates_preservation(self):
        # 25. Verify duplicate names/contents are preserved in order and not collapsed
        nodes = [
            {"name": "dup", "source": "pass1"},
            {"name": "dup", "source": "pass1"},
        ]
        res = chunk_nodes(nodes)
        assert res[0].count("=== dup ===") == 2

    def test_source_verbatim(self):
        # 26. Source code content is preserved verbatim in chunks
        nodes = [{"name": "n1", "source": "special_code_123_abc"}]
        res = chunk_nodes(nodes)
        assert "special_code_123_abc" in res[0]

    def test_skip_empty_nodes(self):
        # 27. Empty nodes do not leave empty chunk spaces or formatting markers
        nodes = [
            {"name": "n1", "source": "pass"},
            {"name": "empty", "source": ""},
            {"name": "n2", "source": "pass"},
        ]
        res = chunk_nodes(nodes)
        assert len(res) == 1
        # Should only contain n1 and n2, with exactly one separator
        assert res[0].count("===") == 4  # 2 headers (start/end marker matches)
        assert res[0].count("\n\n") == 1


class TestPlainStringNodes:
    def test_plain_strings_chunking(self):
        # 28. Plain string nodes (non-dicts) are formatted as str(node) and chunked correctly
        nodes = ["source_chunk_1", "source_chunk_2", "source_chunk_3"]
        res = chunk_nodes(nodes, max_items=2)
        assert len(res) == 2
        assert res[0] == "source_chunk_1\n\nsource_chunk_2"
        assert res[1] == "source_chunk_3"

    def test_plain_strings_empty_ignored(self):
        # 29. Empty/whitespace plain strings are ignored/skipped
        nodes = ["source_chunk_1", "", "   ", "source_chunk_2"]
        res = chunk_nodes(nodes, max_items=2)
        assert len(res) == 1
        assert res[0] == "source_chunk_1\n\nsource_chunk_2"
