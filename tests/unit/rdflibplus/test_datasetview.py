"""Test DatasetView."""

# ruff: noqa: D103, PLR2004
import pytest
from rdflib import Dataset, Graph, Literal, Namespace, URIRef

from pythinfer.rdflibplus import DatasetView

EX = Namespace("http://example.org/")


@pytest.fixture
def g0() -> Graph:
    """Create a named graph with zero triples (for immutability tests)."""
    return Graph(identifier=EX.graph0)


@pytest.fixture
def g1() -> Graph:
    """Create a named graph with one triple."""
    graph = Graph(identifier=EX.graph1)
    graph.add((EX.subject1, EX.predicate1, Literal("object1")))
    return graph


@pytest.fixture
def g2() -> Graph:
    """Create a named graph with three triples."""
    graph = Graph(identifier=EX.graph2)
    graph.add((EX.subject2, EX.predicate2, Literal("object2")))
    graph.add((EX.subject3, EX.predicate3, Literal("object3")))
    graph.add((EX.subject4, EX.predicate4, Literal("object4")))
    return graph


@pytest.fixture
def g3() -> Graph:
    """Create a named graph with five triples."""
    graph = Graph(identifier=EX.graph3)
    graph.add((EX.subject5, EX.predicate5, Literal("object5")))
    graph.add((EX.subject6, EX.predicate6, Literal("object6")))
    graph.add((EX.subject7, EX.predicate7, Literal("object7")))
    graph.add((EX.subject8, EX.predicate8, Literal("object8")))
    graph.add((EX.subject9, EX.predicate9, Literal("object9")))
    return graph


@pytest.fixture
def ds(g1: Graph, g2: Graph, g3: Graph) -> Dataset:
    """Create a Dataset containing all three graphs."""
    dataset = Dataset(default_union=True)
    dataset.graph(g1)
    dataset.graph(g2)
    dataset.graph(g3)
    return dataset


def test_starting_assumptions(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    # Starting assumption: separate graphs with different sizes and with
    # different stores
    assert len(g1) == 1
    assert len(g2) == 3
    assert len(g3) == 5
    assert g1.store != g2.store != g3.store

    # A single Dataset contains all graphs
    assert len(ds.graph(g1.identifier)) == 1
    assert len(ds.graph(g2.identifier)) == 3
    assert len(ds.graph(g3.identifier)) == 5
    assert len(ds) == 9


def test_dataset_behaviour_is_insufficient(
    g1: Graph,
    g3: Graph,
    ds: Dataset,
) -> None:
    # Try to use a new Dataset as a subset view (and show it doesn't work)
    ds2 = Dataset(store=ds.store)
    ds2.add_graph(g1.identifier)
    ds2.add_graph(g3.identifier)

    # First, check that the explicitly added graphs are present:
    assert len(ds2.graph(g1.identifier)) == 1
    assert len(ds2.graph(g3.identifier)) == 5

    # Now, show that it is *not a subset view*: all graphs are there.
    # This would be 6 if Dataset only contained the two graphs added above
    assert len(ds2) == 9


def test_datasetview_basic_usage(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g1.identifier,
            g3.identifier,
        ],
    )

    assert len(ds_view.graph(g1.identifier)) == 1
    assert len(ds_view.graph(g2.identifier)) == 0
    assert len(ds_view.graph(g3.identifier)) == 5
    assert len(ds_view) == 6


def test_datasetview_different_selection(
    g1: Graph,
    g2: Graph,
    g3: Graph,
    ds: Dataset,
) -> None:
    ds_view2 = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g2.identifier,
            g3.identifier,
        ],
    )

    assert len(ds_view2.graph(g1.identifier)) == 0
    assert len(ds_view2.graph(g2.identifier)) == 3
    assert len(ds_view2.graph(g3.identifier)) == 5
    assert len(ds_view2) == 8


def test_quads_method(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g1.identifier,
            g3.identifier,
        ],
    )
    quads = list(ds_view.quads((None, None, None, None)))
    expected_quads = list(ds.quads((None, None, None, None)))
    # Filter expected_quads to only those in g1 and g3
    expected_quads = [
        quad for quad in expected_quads if quad[3] in {g1.identifier, g3.identifier}
    ]
    assert len(expected_quads) == 6
    assert len(quads) == len(expected_quads)
    assert quads == expected_quads


def test_triples_method(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g1.identifier,
            g3.identifier,
        ],
    )
    triples = list(ds_view.triples((None, None, None)))
    expected_triples = list(g1.triples((None, None, None))) + list(
        g3.triples((None, None, None)),
    )

    assert len(expected_triples) == 6
    assert len(triples) == len(expected_triples)
    assert triples == expected_triples

    # Also test with explicit context as kwarg
    triples_ctx = list(
        ds_view.triples((None, None, None), context=g1),
    )
    expected_triples_ctx = list(g1.triples((None, None, None)))
    assert len(triples_ctx) == len(expected_triples_ctx)
    assert triples_ctx == expected_triples_ctx


def test_contains_method(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g1.identifier,
            g3.identifier,
        ],
    )
    # Triples in g1 and g3 should be found
    assert (EX.subject1, EX.predicate1, Literal("object1")) in ds_view
    assert (EX.subject5, EX.predicate5, Literal("object5")) in ds_view

    # Triples in g2 should not be found
    assert (EX.subject2, EX.predicate2, Literal("object2")) not in ds_view


# Below here are currently going to fail because of missing implementation, so this
# is Test-Driven Development.
def test_iterating_over_dataset(g1: Graph, g2: Graph, g3: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g1.identifier,
            g3.identifier,
        ],
    )
    triples = list(ds_view)
    expected_triples = list(g1) + list(g3)

    assert len(expected_triples) == 6
    assert len(triples) == len(expected_triples)
    assert triples == expected_triples


def test_add_graph(g0: Graph, g1: Graph, g2: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g0.identifier,
            g2.identifier,
        ],
    )
    # Try to add a graph to the view
    ds_view.add_graph(g1.identifier)
    assert len(ds_view.graph(g1.identifier)) == 1

    # Check that the original dataset is unaffected
    assert len(ds.graph(g1.identifier)) == 1


def test_remove_graph(g0: Graph, g1: Graph, g2: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g0.identifier,
            g2.identifier,
        ],
    )
    # Try to remove a graph from the view
    ds_view.remove_graph(g2.identifier)
    assert len(ds_view.graph(g2.identifier)) == 0

    # Check that the original dataset is unaffected
    assert len(ds.graph(g2.identifier)) == 3


def test_add_triple(g0: Graph, g1: Graph, g2: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g0.identifier,
            g2.identifier,
        ],
    )
    assert len(ds_view.graph(g0.identifier)) == 0
    assert len(ds.graph(g0.identifier)) == 0

    # Adding a triple to a graph included in the view should work like normal
    ds_view.graph(g0.identifier).add(
        (EX.subjectX, EX.predicateX, Literal("objectX")),
    )
    assert len(ds_view.graph(g0.identifier)) == 1
    # Check that the original dataset reflects the change
    assert len(ds.graph(g0.identifier)) == 1

    # Adding a triple to a graph not included in the view should fail, because
    # it would be counter-intuitive to allow this.
    with pytest.raises(PermissionError):
        ds_view.graph(g1.identifier).add(
            (EX.subjectY, EX.predicateY, Literal("objectY")),
        )


def test_remove_triple(g0: Graph, g1: Graph, g2: Graph, ds: Dataset) -> None:
    ds_view = DatasetView(
        original_ds=ds,
        included_graph_ids=[
            g0.identifier,
            g2.identifier,
        ],
    )
    # Removing a triple from a graph in the view should work like normal
    ds_view.graph(g2.identifier).remove(
        (EX.subject2, EX.predicate2, Literal("object2")),
    )
    assert len(ds_view.graph(g2.identifier)) == 2
    # Check that the original dataset reflects the change
    assert len(ds.graph(g2.identifier)) == 2

    # Removing a triple from a graph not included in the view should fail
    with pytest.raises(PermissionError):
        ds_view.graph(g1.identifier).remove(
            (EX.subject1, EX.predicate1, Literal("object1")),
        )
