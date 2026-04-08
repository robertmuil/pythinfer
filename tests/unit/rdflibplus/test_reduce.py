"""Test reduce function."""

from rdflib import Dataset, Graph, Literal, Namespace

from pythinfer.rdflibplus import DatasetView, reduce


def test_reduce() -> None:
    """Test that reduce works."""
    ds = Dataset()
    g1 = Graph(ds.store, "g1")
    g2 = Graph(ds.store, "g2")
    ex = Namespace("http://example.org/")
    g1.add((ex.s1, ex.p1, Literal("o1")))
    g1.add((ex.s2, ex.p2, Literal("o2")))
    g2.add((ex.s3, ex.p3, Literal("o3")))

    reduced = reduce(ds)
    assert len(reduced) == 3
    assert (ex.s1, ex.p1, Literal("o1")) in reduced
    assert (ex.s2, ex.p2, Literal("o2")) in reduced
    assert (ex.s3, ex.p3, Literal("o3")) in reduced

def test_reduce_empty() -> None:
    """Test that reduce works on empty dataset."""
    ds = Dataset()
    reduced = reduce(ds)
    assert len(reduced) == 0

def test_reduce_with_datasetview() -> None:
    """Test that reduce works on DatasetView exposing only one of two graphs."""
    ds = Dataset()
    ex = Namespace("http://example.org/")
    g1 = ds.graph(ex.g1)
    g2 = ds.graph(ex.g2)
    g1.add((ex.s1, ex.p1, Literal("o1")))
    g2.add((ex.s2, ex.p2, Literal("o2")))

    view = DatasetView(ds, included_graph_ids=[ex.g1])
    reduced = reduce(view)

    assert len(reduced) == 1
    assert (ex.s1, ex.p1, Literal("o1")) in reduced
    assert (ex.s2, ex.p2, Literal("o2")) not in reduced
