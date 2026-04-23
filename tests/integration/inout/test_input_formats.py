"""Tests for multi-format RDF input support.

Verifies that pythinfer can load input files in various RDF serialization
formats (Turtle, TriG, N-Triples, N-Quads, etc.) and that graph-aware
formats like TriG correctly preserve named graph structure.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from rdflib import Dataset, IdentifiedNode, Namespace, Node, URIRef

from pythinfer import Project
from pythinfer.inout import is_quad_file
from pythinfer.merge import merge_graphs
from pythinfer.project import ProjectSpec, create_project

EX = Namespace("http://example.com/")


def _ds_has(ds: Dataset, s: IdentifiedNode, p: URIRef, o: Node) -> bool:
    """Check if a triple exists anywhere in the dataset (any named graph)."""
    return any(ds.quads((s, p, o, None)))


class TestIsQuadFile:
    """Test quad file detection from path extension."""

    def test_quad_extensions(self) -> None:
        assert is_quad_file(Path("data.trig")) is True
        assert is_quad_file(Path("data.nq")) is True
        assert is_quad_file(Path("data.trix")) is True

    def test_triple_extensions(self) -> None:
        assert is_quad_file(Path("data.ttl")) is False
        assert is_quad_file(Path("data.rdf")) is False
        assert is_quad_file(Path("data.nt")) is False
        assert is_quad_file(Path("data.n3")) is False


# -- Merge with different input formats ---------------------------------------

def _write_turtle(path: Path) -> None:
    """Write a small Turtle file."""
    path.write_text(
        "@prefix ex: <http://example.com/> .\n"
        "ex:Alice ex:knows ex:Bob .\n"
    )


def _write_trig(path: Path, *, with_named_graph: bool = True) -> None:
    """Write a small TriG file, optionally with a named graph."""
    if with_named_graph:
        path.write_text(
            "@prefix ex: <http://example.com/> .\n"
            "ex:myGraph {\n"
            "  ex:Alice ex:knows ex:Charlie .\n"
            "  ex:Charlie ex:knows ex:Dave .\n"
            "}\n"
        )
    else:
        path.write_text(
            "@prefix ex: <http://example.com/> .\n"
            "ex:Alice ex:knows ex:Charlie .\n"
        )


def _write_ntriples(path: Path) -> None:
    """Write a small N-Triples file."""
    path.write_text(
        "<http://example.com/Alice> <http://example.com/knows> "
        "<http://example.com/Eve> .\n"
    )


class TestMergeWithTurtleInput:
    """Baseline: merging Turtle files still works."""

    def test_turtle_merge(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_turtle(tmp / "data.ttl")

            project = ProjectSpec(
                name="test-ttl",
                focus=[tmp / "data.ttl"],
                path_self=tmp / "pythinfer.yaml",
            )
            ds = Project.model_validate(project.model_dump()).merge(output=False)

            assert len(ds) > 0
            assert _ds_has(ds, EX.Alice, EX.knows, EX.Bob)


class TestMergeWithTrigInput:
    """Merging TriG files preserves named graph structure."""

    def test_trig_focus_preserves_named_graphs(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_trig(tmp / "data.trig")

            project = Project(
                name="test-trig",
                focus=[tmp / "data.trig"],
                path_self=tmp / "pythinfer.yaml",
            )
            ds = project.merge(output=False)

            # The named graph from the trig file should be present
            graph_ids = {g.identifier for g in ds.graphs()}
            assert EX.myGraph in graph_ids

            # Triples should be present
            assert _ds_has(ds, EX.Alice, EX.knows, EX.Charlie)

    def test_trig_reference_graphs_are_external(self) -> None:
        """Reference trig files should have their graphs marked as external."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_turtle(tmp / "focus.ttl")
            _write_trig(tmp / "vocab.trig")

            project = Project(
                name="test-trig-ref",
                focus=[tmp / "focus.ttl"],
                reference=[tmp / "vocab.trig"],
                path_self=tmp / "pythinfer.yaml",
            )
            # Use merge_graphs directly to get external_gids

            _ds, ext_gids = merge_graphs(project, output=False)

            # The named graph from the trig file should be in external_gids
            assert EX.myGraph in ext_gids

    def test_mixed_turtle_and_trig(self) -> None:
        """Projects with both Turtle and TriG focus files."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_turtle(tmp / "data.ttl")
            _write_trig(tmp / "extra.trig")

            project = Project(
                name="test-mixed",
                focus=[tmp / "data.ttl", tmp / "extra.trig"],
                path_self=tmp / "pythinfer.yaml",
            )
            ds = project.merge(output=False)

            # Both sources should contribute triples
            assert _ds_has(ds, EX.Alice, EX.knows, EX.Bob)
            assert _ds_has(ds, EX.Alice, EX.knows, EX.Charlie)


class TestMergeWithNTriplesInput:
    """Merging N-Triples files."""

    def test_ntriples_merge(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_ntriples(tmp / "data.nt")

            project = Project(
                name="test-nt",
                focus=[tmp / "data.nt"],
                path_self=tmp / "pythinfer.yaml",
            )
            ds = project.merge(output=False)

            assert _ds_has(ds, EX.Alice, EX.knows, EX.Eve)


# -- create_project discovers new extensions -----------------------------------

class TestCreateProjectFindsMultipleFormats:
    """create_project should discover files with various RDF extensions."""

    def test_discovers_trig_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_turtle(tmp / "data.ttl")
            _write_trig(tmp / "extra.trig")

            project = create_project(
                scan_directory=tmp,
                output_path=tmp / "pythinfer.yaml",
            )

            found_names = {p.name for p in project.focus}
            assert "data.ttl" in found_names
            assert "extra.trig" in found_names

    def test_discovers_ntriples_files(self) -> None:
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            _write_ntriples(tmp / "data.nt")

            project = create_project(
                scan_directory=tmp,
                output_path=tmp / "pythinfer.yaml",
            )

            found_names = {p.name for p in project.focus}
            assert "data.nt" in found_names
