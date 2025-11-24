"""Test DatasetView.invert() method."""

from rdflib import Dataset, Namespace

from pythinfer.rdflibplus import DatasetView


def test_invert_returns_complementary_view() -> None:
    """Test that invert() returns a view with all excluded graphs."""
    ds = Dataset()
    EX = Namespace("http://example.org/")

    # Create three graphs
    g1 = ds.graph(EX.graph1)
    g1.add((EX.s1, EX.p1, EX.o1))

    g2 = ds.graph(EX.graph2)
    g2.add((EX.s2, EX.p2, EX.o2))

    g3 = ds.graph(EX.graph3)
    g3.add((EX.s3, EX.p3, EX.o3))

    # Create view with graph1 and graph2
    view = DatasetView(ds, [EX.graph1, EX.graph2])
    assert len(view) == 2

    # Invert should give us only graph3
    inverted = view.invert()
    assert len(inverted) == 1
    assert EX.graph3 in inverted.included_graph_ids
    assert EX.graph1 not in inverted.included_graph_ids
    assert EX.graph2 not in inverted.included_graph_ids


def test_invert_twice_returns_original() -> None:
    """Test that inverting twice gives back the original view."""
    ds = Dataset()
    EX = Namespace("http://example.org/")

    g1 = ds.graph(EX.graph1)
    g1.add((EX.s1, EX.p1, EX.o1))

    g2 = ds.graph(EX.graph2)
    g2.add((EX.s2, EX.p2, EX.o2))

    g3 = ds.graph(EX.graph3)
    g3.add((EX.s3, EX.p3, EX.o3))

    # Create view with graph1 and graph2
    view = DatasetView(ds, [EX.graph1, EX.graph2])

    # Invert twice
    double_inverted = view.invert().invert()

    # Should have same graphs as original (order may differ)
    assert set(double_inverted.included_graph_ids) == set(view.included_graph_ids)
    assert len(double_inverted) == len(view)


def test_invert_empty_view() -> None:
    """Test that inverting an empty view returns all graphs."""
    ds = Dataset()
    EX = Namespace("http://example.org/")

    g1 = ds.graph(EX.graph1)
    g1.add((EX.s1, EX.p1, EX.o1))

    g2 = ds.graph(EX.graph2)
    g2.add((EX.s2, EX.p2, EX.o2))

    # Create empty view
    view = DatasetView(ds, [])
    assert len(view) == 0

    # Invert should give us all graphs
    inverted = view.invert()
    assert len(inverted) == 2
    assert EX.graph1 in inverted.included_graph_ids
    assert EX.graph2 in inverted.included_graph_ids


def test_invert_preserves_store() -> None:
    """Test that inverted view shares the same underlying store."""
    ds = Dataset()
    EX = Namespace("http://example.org/")

    g1 = ds.graph(EX.graph1)
    g1.add((EX.s1, EX.p1, EX.o1))

    g2 = ds.graph(EX.graph2)
    g2.add((EX.s2, EX.p2, EX.o2))

    view = DatasetView(ds, [EX.graph1])
    inverted = view.invert()

    # Verify they share the same store
    assert view.store is inverted.store
    assert view.store is ds.store

    # Modify through inverted view should affect original
    inverted.graph(EX.graph2).add((EX.s3, EX.p3, EX.o3))
    assert len(ds.graph(EX.graph2)) == 2
