"""Extensions to rdflib for pythinfer."""

from collections.abc import Generator

from rdflib import Dataset, Graph, IdentifiedNode
from rdflib.graph import (
    _ContextIdentifierType,  # pyright: ignore[reportPrivateUsage]
    _ContextType,  # pyright: ignore[reportPrivateUsage]
    _OptionalIdentifiedQuadType,  # pyright: ignore[reportPrivateUsage]
    _TripleOrOptionalQuadType,  # pyright: ignore[reportPrivateUsage]
    _TripleOrQuadPatternType,  # pyright: ignore[reportPrivateUsage]
    _TripleType,  # pyright: ignore[reportPrivateUsage]
)


class DatasetView(Dataset):
    """A Dataset subclass that acts as a restricted view on selected named graphs.

    This behaves like a Dataset, but any operations are limited to a specified
    subset of the named graphs in the original Dataset. The data is *not copied*, the
    same underlying store is used, so changes to the graphs in the view are reflected
    in the original Dataset, and vice versa.

    Adding and removing graphs from the view abides by the original Dataset API, except
    that only graphs in the included set can be accessed. Trying to add or remove a
    graph not in the included set will raise a PermissionError.

    To include or exclude graphs from the view after creation, use the `include_graph`
    and `exclude_graph` methods.
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
        _id = identifier.identifier if isinstance(identifier, Graph) else identifier
        if _id in self.included_graph_ids:
            return super().graph(identifier, base=base)
        msg = f"Graph {_id} is not visible in this view."
        raise PermissionError(msg)

    def __len__(self) -> int:
        """Get the total number of triples in the view."""
        total = 0
        for gid in self.included_graph_ids:
            total += len(super().graph(gid))
        return total

    def graphs(
        self,
        triple: _TripleOrQuadPatternType | None = None,
    ) -> Generator[Graph, None, None]:
        """Return graphs in this view, optionally filtered by triple pattern."""
        # Get all graphs from parent, but only yield those in our included list
        for g in super().graphs(triple):
            if g.identifier in self.included_graph_ids:
                yield g

    def quads(
        self,
        quad: _TripleOrQuadPatternType | None = None,
    ) -> Generator[_OptionalIdentifiedQuadType, None, None]:
        """Return quads matching the pattern from included graphs only."""
        for q in super().quads(quad):
            if q[3] in self.included_graph_ids:
                yield q

    # The type-checkers don't like that we are not handling the overloads that
    # exist for the triples method, which handle graph Paths. TODO.
    def triples(
        self,
        triple_or_quad: _TripleOrQuadPatternType,
        context: _ContextType | None = None,
    ) -> Generator[_TripleType, None, None]:
        """Return triples matching the pattern from included graphs only."""
        if context is not None:
            # If context is specified, only return triples from that graph
            # if it's in the included graphs
            if context.identifier in self.included_graph_ids:
                yield from context.triples(triple_or_quad[0:3])
        else:
            # Check if a quad pattern was passed (4 elements with graph ID)
            if len(triple_or_quad) == 4 and triple_or_quad[3] is not None:
                # Quad pattern with specific graph - only query that graph
                graph_id = triple_or_quad[3]
                if hasattr(graph_id, "identifier"):
                    graph_id = graph_id.identifier  # type: ignore[union-attr]
                if graph_id in self.included_graph_ids:
                    g = super().graph(graph_id)
                    yield from g.triples(triple_or_quad[:3])  # type: ignore[arg-type]
            else:
                # No context and no graph specified in pattern - return from all
                # Call triples() on each graph directly to avoid triggering rdflib's
                # internal contexts() enumeration which tries to access default graph.
                triple_pattern = (
                    triple_or_quad[:3] if len(triple_or_quad) == 4 else triple_or_quad
                )  # type: ignore[misc]
                for gid in self.included_graph_ids:
                    g = super().graph(gid)
                    yield from g.triples(triple_pattern)  # type: ignore[arg-type]

    def add(
        self: "DatasetView",
        triple_or_quad: _TripleOrOptionalQuadType,
    ) -> "DatasetView":
        """Add a triple or quad to the store.

        if a triple is given it is added to the default context

        If the graph is not in the included set, raise PermissionError.
        """
        graph_id = self.default_graph.identifier
        if len(triple_or_quad) == 4:  # noqa: PLR2004
            graph_id = triple_or_quad[3]
        if graph_id not in self.included_graph_ids:
            msg = f"Cannot add to graph {graph_id}: not visible in this view."
            raise PermissionError(msg)
        return super().add(triple_or_quad)

    def remove(
        self: "DatasetView",
        triple_or_quad: _TripleOrQuadPatternType,
    ) -> "DatasetView":
        """Remove a triple or quads.

        If the graph is not in the included set, raise PermissionError.
        The graph is either that specified explicitly in the quad, or the default graph

        Otherwise, behaviour is as per Dataset.remove():
        If a triple is given it is removed from all named graphs.
        If a quad is given it is removed from the specified named graph.

        """
        graph_id = self.default_graph.identifier
        if len(triple_or_quad) == 4:  # noqa: PLR2004
            graph_id = triple_or_quad[3]
        if graph_id not in self.included_graph_ids:
            msg = f"Cannot add to graph {graph_id}: not visible in this view."
            raise PermissionError(msg)
        return super().remove(triple_or_quad)

    def remove_graph(
        self,
        g: _ContextIdentifierType | _ContextType | str | None,
    ) -> "DatasetView":
        """Remove a graph from the store, if visible in this view."""
        graph_id = g
        if isinstance(g, Graph):
            graph_id = g.identifier
        elif g is None:
            graph_id = self.default_graph.identifier

        if graph_id not in self.included_graph_ids:
            msg = f"Cannot remove graph {graph_id}: not visible in this view."
            raise PermissionError(msg)
        return super().remove_graph(g)

    def serialize(
        self,
        destination: str | None = None,
        format: str = "xml",  # noqa: A002
        base: str | None = None,
        encoding: str | None = None,
        **args: object,
    ) -> str:
        """Serialize the DatasetView to a destination.

        Only graphs in the included_graph_ids will be serialized. This requires
        creating a temporary Dataset to work around rdflib's serializers accessing
        the store directly instead of using our overridden quads() method.

        The signature matches rdflib.Dataset.serialize().
        """
        # Create a temporary dataset with only the included graphs.
        # This is necessary because rdflib serializers bypass our quads() override
        # and access the store directly.
        temp_ds = Dataset()
        for s, p, o, c in self.quads():
            temp_ds.add((s, p, o, c))  # type: ignore[arg-type]

        # Serialize the temporary dataset
        return temp_ds.serialize(  # type: ignore[return-value]
            destination=destination,
            format=format,
            base=base,
            encoding=encoding,
            **args,
        )
