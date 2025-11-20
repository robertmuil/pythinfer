"""Explore the idea of Dataset views in rdflib."""

# ruff: noqa: T201, S101, PLR2004, INP001
from rdflib import Dataset, Graph, IdentifiedNode, Literal, Namespace, URIRef

EX = Namespace("http://example.org/")

# Create some named graphs
g1 = Graph(identifier=URIRef("http://example.org/graph1"))
g1.add((EX.subject1, EX.predicate1, Literal("object1")))

g2 = Graph(identifier=URIRef("http://example.org/graph2"))
g2.add((EX.subject2, EX.predicate2, Literal("object2")))
g2.add((EX.subject3, EX.predicate3, Literal("object3")))
g2.add((EX.subject4, EX.predicate4, Literal("object4")))

g3 = Graph(identifier=URIRef("http://example.org/graph3"))
g3.add((EX.subject5, EX.predicate5, Literal("object5")))
g3.add((EX.subject6, EX.predicate6, Literal("object6")))
g3.add((EX.subject7, EX.predicate7, Literal("object7")))
g3.add((EX.subject8, EX.predicate8, Literal("object8")))
g3.add((EX.subject9, EX.predicate9, Literal("object9")))

###
# Start demonstration
###

# Starting assumption: separate graphs with different sizes and with different stores
assert len(g1) == 1
assert len(g2) == 3
assert len(g3) == 5
assert g1.store != g2.store != g3.store

ds = Dataset()
ds.graph(g1)
ds.graph(g2)
ds.graph(g3)
assert len(ds.graph(g1.identifier)) == 1
assert len(ds.graph(g2.identifier)) == 3
assert len(ds.graph(g3.identifier)) == 5
assert len(ds) == 9

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


# Simple implementation of a View that *contains* a dataset
class DatasetViewAsContainer:
    """A simple view on a Dataset containing only selected named graphs."""

    def __init__(
        self,
        original_ds: Dataset,
        included_graph_ids: list[IdentifiedNode],
    ) -> None:
        """Initialize the Dataset view containing a pointer to the original Dataset."""
        self.original_ds = original_ds
        self.included_graph_ids = included_graph_ids

    def graph(self, gid: IdentifiedNode) -> Graph:
        """Get a named graph from the view."""
        if gid in self.included_graph_ids:
            return self.original_ds.graph(gid)
        return Graph(identifier=gid)  # empty graph

    def __len__(self) -> int:
        """Get the total number of triples in the view."""
        total = 0
        for gid in self.included_graph_ids:
            total += len(self.original_ds.graph(gid))
        return total


# NB: this is *not at all* complete:
# TODO: override more Dataset methods to ensure correct behaviour.
# TODO: disallow modification of the view.
# Implementation of a DatasetView that is a subclass of Dataset...
class DatasetViewAsDataset(Dataset):
    """A Dataset subclass that acts as a view on selected named graphs."""

    def __init__(
        self, original_ds: Dataset, included_graph_ids: list[IdentifiedNode]
    ) -> None:
        """Initialize the Dataset view containing a pointer to the original Dataset."""
        super().__init__(store=original_ds.store)
        self.included_graph_ids = included_graph_ids

    def graph(
        self,
        identifier: IdentifiedNode | Graph | str | None = None,
        base: str | None = None,
    ) -> Graph:
        """Get a named graph from the view."""
        if identifier in self.included_graph_ids:
            return super().graph(identifier, base=base)

        _id = identifier if not isinstance(identifier, Graph) else identifier.identifier
        return Graph(identifier=_id, base=base)  # empty graph

    def __len__(self) -> int:
        """Get the total number of triples in the view."""
        total = 0
        for gid in self.included_graph_ids:
            total += len(super().graph(gid))
        return total


# Desired behaviour (not supported by rdflib Dataset):
ds_view = DatasetViewAsContainer(
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

# Desired behaviour also for Dataset subclass view:
ds_view2 = DatasetViewAsDataset(
    original_ds=ds,
    included_graph_ids=[
        g1.identifier,
        g3.identifier,
    ],
)

assert len(ds_view2.graph(g1.identifier)) == 1
assert len(ds_view2.graph(g2.identifier)) == 0
assert len(ds_view2.graph(g3.identifier)) == 5
assert len(ds_view2) == 6

print("✅ Dataset view exploration script completed successfully.")
