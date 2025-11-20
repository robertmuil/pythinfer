"""Extensions to rdflib for pythinfer."""

from rdflib import Dataset, Graph, IdentifiedNode


# NB: this is *not at all* complete:
# TODO: override more Dataset methods to ensure correct behaviour.
# TODO: disallow modification of the view.
# Implementation of a DatasetView that is a subclass of Dataset...
class DatasetView(Dataset):
    """A Dataset subclass that acts as a view on selected named graphs."""

    def __init__(
        self,
        original_ds: Dataset,
        included_graph_ids: list[IdentifiedNode],
    ) -> None:
        """Initialize the Dataset view containing a pointer to the original Dataset."""
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
