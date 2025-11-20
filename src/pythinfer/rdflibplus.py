"""Extensions to rdflib for pythinfer."""

from rdflib import Dataset, Graph, IdentifiedNode


# NB: this is *not at all* complete:
# TODO: override more Dataset methods to ensure correct behaviour.
# TODO: implement immutable mode.
# TODO: OR rename it to Datasubset
# Implementation of a DatasetView that is a subclass of Dataset...
class DatasetView(Dataset):
    """A Dataset subclass that acts as a view on selected named graphs.

    This behaves like a Dataset, but any operations are limited to a specified
    subset of the named graphs in the original Dataset.

    Removing a graph from the view does *not* remove it from the original Dataset, it
    just makes it invisible in the view. This is a slight deviation Dataset's API, which
    allows graphs to be removed entirely. To do that, simply remove the graph from the
    original Dataset.
    """

    def __init__(
        self,
        original_ds: Dataset,
        included_graph_ids: list[IdentifiedNode],
        *,
        immutable: bool = False,
    ) -> None:
        """Initialize the Dataset view containing a pointer to the original Dataset."""
        self.immutable = immutable
        if self.immutable:
            msg = "Immutable DatasetView is not yet implemented."
            raise NotImplementedError(msg)
        super().__init__(
            store=original_ds.store,
            default_union=original_ds.default_union,
        )
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
