"""Unit tests for pure-logic functions in pythinfer.explore."""

import re
from pathlib import Path

import pytest
from rdflib import Graph, Namespace
from typer.testing import CliRunner

from pythinfer.cli import app
from pythinfer.explore import (
    CompareResult,
    _bind_namespaces,
    _clip_triple_line,
    _compile_filter,
    _compute_triple_col_widths,
    _filter_matches,
    _FilterState,
    _list_filter_files,
    _shorten,
    _unbind_namespace,
    build_comparison_views,
    build_explore_views,
    compare_graphs,
    format_triples,
    load_graph,
)

EX = Namespace("http://example.org/")


def _make_ttl(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content)
    return p


# ---------- load_graph / format_triples / _shorten ----------


class TestLoadGraph:
    def test_loads_turtle(self, tmp_path: Path) -> None:
        f = _make_ttl(tmp_path, "g.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        g = load_graph(f)
        assert len(g) == 1

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(Exception):  # noqa: B017
            load_graph(tmp_path / "missing.ttl")


class TestShorten:
    def test_with_prefix(self) -> None:
        g = Graph()
        g.bind("ex", EX)
        result = _shorten(EX.Thing, g.namespace_manager)
        assert result == "ex:Thing"

    def test_without_prefix(self) -> None:
        g = Graph()
        uri = EX.Something
        result = _shorten(uri, g.namespace_manager)
        # Falls back to str representation when no prefix registered
        assert "example.org" in result


class TestFormatTriples:
    def test_formats_sorted(self, tmp_path: Path) -> None:
        f = _make_ttl(tmp_path, "g.ttl", """\
@prefix ex: <http://example.org/> .
ex:b ex:rel ex:c .
ex:a ex:rel ex:d .
""")
        g = load_graph(f)
        lines = format_triples(g)
        assert len(lines) == 2
        # Sorted by string representation, so ex:a should come before ex:b
        assert "a" in lines[0]
        assert "b" in lines[1]

    def test_empty_graph(self) -> None:
        g = Graph()
        assert format_triples(g) == []


# ---------- _compute_triple_col_widths / _clip_triple_line ----------


class TestComputeTripleColWidths:
    def test_returns_none_when_fits(self) -> None:
        lines = ["s  p  o"]
        assert _compute_triple_col_widths(lines, 100) is None

    def test_returns_none_for_empty(self) -> None:
        assert _compute_triple_col_widths([], 80) is None

    def test_returns_none_for_non_triple(self) -> None:
        lines = ["just a plain line"]
        assert _compute_triple_col_widths(lines, 10) is None

    def test_distributes_when_too_wide(self) -> None:
        lines = ["short  medium_field  " + "x" * 200]
        result = _compute_triple_col_widths(lines, 40)
        assert result is not None
        assert len(result) == 3
        assert all(w > 0 for w in result)


class TestClipTripleLine:
    def test_clips_fields(self) -> None:
        line = "subject  predicate  object_value"
        result = _clip_triple_line(line, [4, 4, 6])
        parts = result.split("  ")
        assert len(parts) == 3
        assert all(len(p) <= w for p, w in zip(parts, [4, 4, 6], strict=False))

    def test_non_triple_returned_as_is(self) -> None:
        line = "no double space separation"
        assert _clip_triple_line(line, [5, 5, 5]) == line


# ---------- _bind_namespaces / _unbind_namespace ----------


class TestBindNamespaces:
    def test_copies_bindings(self) -> None:
        src = Graph()
        src.bind("ex", EX)
        target = Graph()
        _bind_namespaces(target, src)
        prefixes = {str(p): str(ns) for p, ns in target.namespaces()}
        assert prefixes.get("ex") == str(EX)

    def test_no_override(self) -> None:
        other = Namespace("http://other.org/")
        target = Graph()
        target.bind("ex", other)
        src = Graph()
        src.bind("ex", EX)
        _bind_namespaces(target, src)
        prefixes = {str(p): str(ns) for p, ns in target.namespaces()}
        # override=False means original binding kept
        assert prefixes["ex"] == str(other)


class TestUnbindNamespace:
    def test_removes_binding(self) -> None:
        g = Graph()
        g.bind("test", EX)
        assert _unbind_namespace(g, "test") is True
        prefixes = dict(g.namespaces())
        assert "test" not in prefixes

    def test_missing_prefix_returns_false(self) -> None:
        g = Graph()
        assert _unbind_namespace(g, "nonexistent") is False


# ---------- compare_graphs / build_*_views ----------


class TestCompareGraphs:
    def test_identical_graphs(self, tmp_path: Path) -> None:
        content = """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
"""
        f1 = _make_ttl(tmp_path, "left.ttl", content)
        f2 = _make_ttl(tmp_path, "right.ttl", content)
        result = compare_graphs(f1, f2)
        assert isinstance(result, CompareResult)
        assert len(result.only_left) == 0
        assert len(result.only_right) == 0
        assert len(result.both) == 1
        assert len(result.union) == 1

    def test_disjoint_graphs(self, tmp_path: Path) -> None:
        f1 = _make_ttl(tmp_path, "left.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        f2 = _make_ttl(tmp_path, "right.ttl", """\
@prefix ex: <http://example.org/> .
ex:x ex:y ex:z .
""")
        result = compare_graphs(f1, f2)
        assert len(result.only_left) == 1
        assert len(result.only_right) == 1
        assert len(result.both) == 0
        assert len(result.union) == 2

    def test_overlapping_graphs(self, tmp_path: Path) -> None:
        f1 = _make_ttl(tmp_path, "left.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
ex:shared ex:rel ex:val .
""")
        f2 = _make_ttl(tmp_path, "right.ttl", """\
@prefix ex: <http://example.org/> .
ex:x ex:y ex:z .
ex:shared ex:rel ex:val .
""")
        result = compare_graphs(f1, f2)
        assert len(result.only_left) == 1
        assert len(result.only_right) == 1
        assert len(result.both) == 1
        assert len(result.union) == 3
        assert result.left_count == 2
        assert result.right_count == 2


class TestBuildComparisonViews:
    def test_returns_four_views(self, tmp_path: Path) -> None:
        f1 = _make_ttl(tmp_path, "left.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        f2 = _make_ttl(tmp_path, "right.ttl", """\
@prefix ex: <http://example.org/> .
ex:x ex:y ex:z .
""")
        result = compare_graphs(f1, f2)
        views = build_comparison_views(result)
        assert set(views.keys()) == {"left", "right", "both", "union"}
        for key, (title, lines) in views.items():
            assert isinstance(title, str)
            assert isinstance(lines, list)

    def test_view_titles_include_filenames(self, tmp_path: Path) -> None:
        f1 = _make_ttl(tmp_path, "alpha.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        f2 = _make_ttl(tmp_path, "beta.ttl", """\
@prefix ex: <http://example.org/> .
ex:x ex:y ex:z .
""")
        result = compare_graphs(f1, f2)
        views = build_comparison_views(result)
        assert "alpha.ttl" in views["left"][0]
        assert "beta.ttl" in views["right"][0]


class TestBuildExploreViews:
    def test_single_view(self) -> None:
        g = Graph()
        g.bind("ex", EX)
        g.add((EX.a, EX.b, EX.c))
        views = build_explore_views(g, label="Test")
        assert "both" in views
        assert "Test" in views["both"][0]
        assert len(views["both"][1]) == 1

    def test_default_label(self) -> None:
        g = Graph()
        views = build_explore_views(g)
        assert "Graph" in views["both"][0]


# ---------- _compile_filter / _filter_matches / _FilterState ----------


class TestCompileFilter:
    def test_simple_pattern(self) -> None:
        f = _compile_filter("hello")
        assert f is not None
        assert f.field is None
        assert f.pattern.flags & re.IGNORECASE  # lowercase → case-insensitive

    def test_uppercase_is_case_sensitive(self) -> None:
        f = _compile_filter("Hello")
        assert f is not None
        assert not (f.pattern.flags & re.IGNORECASE)

    def test_field_prefix_s(self) -> None:
        f = _compile_filter("s=person")
        assert f is not None
        assert f.field == "s"
        assert f.source_text == "s=person"

    def test_field_prefix_p(self) -> None:
        f = _compile_filter("p=type")
        assert f is not None
        assert f.field == "p"

    def test_field_prefix_o(self) -> None:
        f = _compile_filter("o=value")
        assert f is not None
        assert f.field == "o"

    def test_invalid_regex(self) -> None:
        assert _compile_filter("[invalid") is None

    def test_empty_after_prefix(self) -> None:
        assert _compile_filter("s=") is None

    def test_empty_string(self) -> None:
        assert _compile_filter("") is None


class TestFilterMatches:
    def test_whole_line_match(self) -> None:
        f = _compile_filter("hello")
        assert f is not None
        assert _filter_matches(f, "say hello world") is True
        assert _filter_matches(f, "goodbye world") is False

    def test_field_subject_match(self) -> None:
        f = _compile_filter("s=alice")
        assert f is not None
        # Fields separated by double-space
        assert _filter_matches(f, "alice  knows  bob") is True
        assert _filter_matches(f, "bob  knows  alice") is False

    def test_field_object_match(self) -> None:
        f = _compile_filter("o=alice")
        assert f is not None
        assert _filter_matches(f, "bob  knows  alice") is True
        assert _filter_matches(f, "alice  knows  bob") is False

    def test_field_index_out_of_range(self) -> None:
        f = _compile_filter("o=test")
        assert f is not None
        assert _filter_matches(f, "no double spaces") is False


class TestFilterState:
    def test_empty_state(self) -> None:
        fs = _FilterState()
        assert not fs.active
        assert not fs.multi
        assert fs.apply(["a", "b"]) == ["a", "b"]

    def test_single_filter(self) -> None:
        fs = _FilterState()
        f = _compile_filter("hello")
        assert f is not None
        fs.set_single(f)
        assert fs.active
        assert not fs.multi
        result = fs.apply(["hello world", "goodbye", "say hello"])
        assert result == ["hello world", "say hello"]

    def test_add_multiple(self) -> None:
        fs = _FilterState()
        f1 = _compile_filter("a")
        f2 = _compile_filter("b")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)
        assert fs.multi
        # Both filters must match (AND logic)
        result = fs.apply(["ab", "a", "b", "c"])
        assert result == ["ab"]

    def test_clear(self) -> None:
        fs = _FilterState()
        f = _compile_filter("x")
        assert f is not None
        fs.add(f)
        fs.clear()
        assert not fs.active

    def test_remove(self) -> None:
        fs = _FilterState()
        f1 = _compile_filter("a")
        f2 = _compile_filter("b")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)
        fs.remove(0)
        assert len(fs.filters) == 1
        assert fs.filters[0].source_text == "b"

    def test_remove_invalid_index(self) -> None:
        fs = _FilterState()
        fs.remove(5)  # should not raise

    def test_swap(self) -> None:
        fs = _FilterState()
        f1 = _compile_filter("first")
        f2 = _compile_filter("second")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)
        fs.swap(0, 1)
        assert fs.filters[0].source_text == "second"
        assert fs.filters[1].source_text == "first"

    def test_swap_invalid_index(self) -> None:
        fs = _FilterState()
        f = _compile_filter("x")
        assert f is not None
        fs.add(f)
        fs.swap(0, 5)  # should not raise
        assert fs.filters[0].source_text == "x"

    def test_summary_no_filters(self) -> None:
        fs = _FilterState()
        assert fs.summary(10, 10) == ""

    def test_summary_with_filters(self) -> None:
        fs = _FilterState()
        f = _compile_filter("test")
        assert f is not None
        fs.add(f)
        s = fs.summary(100, 42)
        assert "test" in s
        assert "42/100" in s

    def test_combined_pattern(self) -> None:
        fs = _FilterState()
        f1 = _compile_filter("alpha")
        f2 = _compile_filter("beta")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)
        pat = fs.combined_pattern()
        assert pat is not None
        assert pat.search("alpha") is not None
        assert pat.search("beta") is not None

    def test_combined_pattern_excludes_field_filters(self) -> None:
        fs = _FilterState()
        f = _compile_filter("s=subject")
        assert f is not None
        fs.add(f)
        assert fs.combined_pattern() is None

    def test_field_patterns(self) -> None:
        fs = _FilterState()
        f1 = _compile_filter("s=alice")
        f2 = _compile_filter("p=knows")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)
        fp = fs.field_patterns()
        assert "s" in fp
        assert "p" in fp
        assert "o" not in fp

    def test_save_and_load(self, tmp_path: Path) -> None:
        fs = _FilterState()
        f1 = _compile_filter("alpha")
        f2 = _compile_filter("s=beta")
        assert f1 is not None and f2 is not None
        fs.add(f1)
        fs.add(f2)

        path = tmp_path / "test.filters"
        fs.save(path)
        assert path.exists()

        fs2 = _FilterState()
        fs2.load(path)
        assert len(fs2.filters) == 2
        assert fs2.filters[0].source_text == "alpha"
        assert fs2.filters[1].source_text == "s=beta"
        assert fs2.filters[1].field == "s"

    def test_load_skips_invalid_regex(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.filters"
        path.write_text("[invalid\ngood\n")
        fs = _FilterState()
        fs.load(path)
        assert len(fs.filters) == 1
        assert fs.filters[0].source_text == "good"

    def test_load_skips_blank_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "blank.filters"
        path.write_text("a\n\n  \nb\n")
        fs = _FilterState()
        fs.load(path)
        assert len(fs.filters) == 2


# ---------- _list_filter_files ----------


class TestListFilterFiles:
    def test_finds_filter_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.filters").write_text("x\n")
        (tmp_path / "b.filters").write_text("y\n")
        (tmp_path / "c.txt").write_text("z\n")
        result = _list_filter_files(tmp_path)
        assert len(result) == 2
        names = [p.name for p in result]
        assert "a.filters" in names
        assert "b.filters" in names

    def test_returns_sorted(self, tmp_path: Path) -> None:
        (tmp_path / "z.filters").write_text("")
        (tmp_path / "a.filters").write_text("")
        result = _list_filter_files(tmp_path)
        assert result[0].name == "a.filters"

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        result = _list_filter_files(tmp_path / "nope")
        assert result == []

    def test_empty_dir(self, tmp_path: Path) -> None:
        assert _list_filter_files(tmp_path) == []


# ---------- CLI compare / explore commands ----------


class TestCompareCLI:
    def test_compare_no_interactive(self, tmp_path: Path) -> None:
        """compare --no-interactive prints summary without launching curses."""
        f1 = _make_ttl(tmp_path, "left.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
ex:shared ex:rel ex:val .
""")
        f2 = _make_ttl(tmp_path, "right.ttl", """\
@prefix ex: <http://example.org/> .
ex:x ex:y ex:z .
ex:shared ex:rel ex:val .
""")
        runner = CliRunner()
        result = runner.invoke(app, ["compare", "--no-interactive", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "Intersection (both):" in result.output
        assert "Only in left:" in result.output
        assert "Only in right:" in result.output
        assert "Union (all):" in result.output

    def test_compare_file_not_found(self, tmp_path: Path) -> None:
        f1 = _make_ttl(tmp_path, "left.ttl", """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
""")
        runner = CliRunner()
        result = runner.invoke(app, ["compare", "--no-interactive", str(f1), str(tmp_path / "missing.ttl")])
        assert result.exit_code == 1

    def test_compare_identical(self, tmp_path: Path) -> None:
        content = """\
@prefix ex: <http://example.org/> .
ex:a ex:b ex:c .
"""
        f1 = _make_ttl(tmp_path, "a.ttl", content)
        f2 = _make_ttl(tmp_path, "b.ttl", content)
        runner = CliRunner()
        result = runner.invoke(app, ["compare", "-I", str(f1), str(f2)])
        assert result.exit_code == 0
        assert "Only in left:           0" in result.output
        assert "Only in right:          0" in result.output


class TestExploreCLI:
    def test_explore_file_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["explore", "/nonexistent/file.ttl"])
        assert result.exit_code == 1
