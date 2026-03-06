"""Tests for the Python API."""

from pathlib import Path

import pytest
from rdflib import Dataset, Graph

from pythinfer import Project

EXAMPLE_DIR = Path("example_projects/eg0-basic")


class TestProjectDiscover:
    """Test Project.discover() from an example project directory."""

    def test_discover_returns_project(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Discover a project from the example directory."""
        monkeypatch.chdir(EXAMPLE_DIR)
        project = Project.discover()
        assert isinstance(project, Project)
        assert project.name is not None

    def test_discover_has_focus_files(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Discovered project should have focus files."""
        monkeypatch.chdir(EXAMPLE_DIR)
        project = Project.discover()
        assert len(project.focus) > 0

    def test_discover_has_reference_attribute(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Discovered project should expose a reference list."""
        monkeypatch.chdir(EXAMPLE_DIR)
        project = Project.discover()
        assert isinstance(project.reference, list)


@pytest.fixture
def discovered_project(monkeypatch: pytest.MonkeyPatch) -> Project:
    """Return a discovered Project from the eg0-basic example directory."""
    monkeypatch.chdir(EXAMPLE_DIR)
    return Project.discover()


class TestProjectMerge:
    """Test Project.merge() method."""

    def test_merge_returns_dataset(self, discovered_project: Project) -> None:
        """merge() should return an rdflib Dataset."""
        ds = discovered_project.merge()
        assert isinstance(ds, Dataset)

    def test_merge_has_triples(self, discovered_project: Project) -> None:
        """Merged dataset should contain triples."""
        ds = discovered_project.merge()
        assert len(ds) > 0

    def test_merge_has_named_graphs(self, discovered_project: Project) -> None:
        """Merged dataset should contain named graphs."""
        ds = discovered_project.merge()
        assert len(list(ds.graphs())) > 0


class TestProjectInfer:
    """Test Project.infer() method."""

    def test_infer_returns_dataset(self, discovered_project: Project) -> None:
        """infer() should return an rdflib Dataset."""
        ds = discovered_project.infer()
        assert isinstance(ds, Dataset)

    def test_infer_has_triples(self, discovered_project: Project) -> None:
        """Inferred dataset should contain triples."""
        ds = discovered_project.infer()
        assert len(ds) > 0

    def test_infer_has_named_graphs(self, discovered_project: Project) -> None:
        """Inferred dataset should contain named graphs."""
        ds = discovered_project.infer()
        assert len(list(ds.graphs())) > 0

    def test_infer_adds_triples_beyond_merge(self, discovered_project: Project) -> None:
        """Inferred dataset should have more triples than the merged dataset."""
        ds_merged = discovered_project.merge()
        ds_inferred = discovered_project.infer()
        assert len(ds_inferred) > len(ds_merged)


class TestQueryOnInferredDataset:
    """Test querying the inferred dataset as shown in the README examples."""

    def test_query_named_graphs(self, discovered_project: Project) -> None:
        """Query across named graphs should return results."""
        ds = discovered_project.infer()
        results = ds.query(
            "SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } } LIMIT 5"
        )
        rows = list(results)
        assert len(rows) > 0

    def test_strip_to_single_graph(self, discovered_project: Project) -> None:
        """Stripping dataset to a single Graph should preserve triples."""
        ds = discovered_project.infer()
        g = Graph()
        for s, p, o, _ctx in ds.quads():
            g.add((s, p, o))
        assert len(g) > 0

    def test_query_stripped_graph_for_types(self, discovered_project: Project) -> None:
        """Querying the stripped graph for rdf:type triples should return results."""
        ds = discovered_project.infer()
        g = Graph()
        for s, p, o, _ctx in ds.quads():
            g.add((s, p, o))
        results = g.query("SELECT * WHERE { ?s a ?type } LIMIT 5")
        rows = list(results)
        assert len(rows) > 0



