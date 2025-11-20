"""Extensions to rdflib for pythinfer."""

from collections.abc import Generator

from rdflib import Dataset, Graph, IdentifiedNode
from rdflib.graph import (
    _ContextType,  # pyright: ignore[reportPrivateUsage]
    _OptionalIdentifiedQuadType,
    _TripleOrQuadPatternType,
    _TripleType,
)


# NB: this is *not at all* complete:
# TODO: override more Dataset methods to ensure correct behaviour.
class DatasetView(Dataset):
    """A Dataset subclass that acts as a restricted view on selected named graphs.

    This behaves like a Dataset, but any operations are limited to a specified
    subset of the named graphs in the original Dataset. The data is *not copied*, the
    same underlying store is used, so changes to the graphs in the view are reflected
    in the original Dataset, and vice versa.

    Removing a graph from the view does *not* remove it from the original Dataset, it
    just makes it invisible in the view. This is a slight deviation Dataset's API, which
    allows graphs to be removed entirely. To do that, simply remove the graph from the
    original Dataset.
    """

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

    def quads(
        self,
        quad: _TripleOrQuadPatternType | None = None,
    ) -> Generator[_OptionalIdentifiedQuadType, None, None]:
        """Return quads matching the pattern from included graphs only."""
        for q in super().quads(quad):
            if q[3] in self.included_graph_ids:
                yield q

    def triples(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        triple_or_quad: _TripleOrQuadPatternType,
        context: _ContextType | None = None,
    ) -> Generator[_TripleType, None, None]:
        """Return triples matching the pattern from included graphs only."""
        if context is not None:
            # If context is specified, only return triples from that graph
            # if it's in the included graphs
            if context.identifier in self.included_graph_ids:
                yield from super().triples(triple_or_quad, context=context)
        else:
            # If no context specified, return triples from all included graphs
            for gid in self.included_graph_ids:
                yield from super().triples(triple_or_quad, context=self.graph(gid))
