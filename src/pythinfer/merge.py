"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

from dataclasses import dataclass

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import ConjunctiveGraph

from .inout import Project


@dataclass
class MergedGraph:
    """Container for merged and inferred graphs.

    Probably should just use ConjunctiveGraph directly.

    data, vocab_internal, vocab_external are the merged input graphs.
    vocab_external_inferences is the set of inferences over external vocabulary graph.
    full_inferences is the set of inferences over full all data and vocabularies.
    """

    data: ConjunctiveGraph
    vocab_internal: ConjunctiveGraph
    vocab_external: ConjunctiveGraph

    # This is not necessary, but kept for efficiency as accessed multiple times.
    merged: ConjunctiveGraph

    vocab_external_inferences: ConjunctiveGraph | None = None
    full_inferences: ConjunctiveGraph | None = None

    @property
    def full(self) -> ConjunctiveGraph:
        """Get the full inferred graph."""
        if self.full_inferences is None:
            msg = "Full inferences have not been computed yet."
            raise ValueError(msg)

        _full = ConjunctiveGraph()

        for triple in self.merged:
            _full.add(triple)
        for triple in self.full_inferences:
            _full.add(triple)

        return _full

    @property
    def final(self) -> ConjunctiveGraph:
        """Get the final graph: full inferences minus external vocabulary triples.

        Returns everything from full_inferences except triples from vocab_external
        and vocab_external_inferences, preserving named graph sources.
        """
        if self.full_inferences is None:
            msg = "Full inferences have not been computed yet."
            raise ValueError(msg)

        # Get identifiers of external vocab graphs to exclude
        external_ids = {
            context.identifier for context in self.vocab_external.contexts()
        }
        external_inferences_ids = (
            {
                context.identifier
                for context in self.vocab_external_inferences.contexts()
            }
            if self.vocab_external_inferences
            else set()
        )
        exclude_ids = external_ids | external_inferences_ids

        _final = ConjunctiveGraph()

        # Add all triples from merged (preserving named graphs)
        for s, p, o, c in self.merged.quads():
            if c and c.identifier not in exclude_ids:
                _final.add((s, p, o, c))

        # Add inferred triples not from external vocab (preserving named graphs)
        for s, p, o, c in self.full_inferences.quads():
            if c and c.identifier not in exclude_ids:
                _final.add((s, p, o, c))

        return _final


def merge_graphs(
    cfg: Project,
) -> MergedGraph:
    """Merge graphs: preserve named graphs for each input and keep graph types separate.

    Returns a tuple of (data, vocabs_internal, vocabs_external) conjuctive graphs.
    """
    external = ConjunctiveGraph()
    internal = ConjunctiveGraph()
    data = ConjunctiveGraph()
    for src in cfg.paths_vocab_ext:
        external.parse(src, format="turtle", publicID=str(src))
    for src in cfg.paths_vocab_int:
        internal.parse(src, format="turtle", publicID=str(src))
    for src in cfg.paths_data:
        data.parse(src, format="turtle", publicID=str(src))

    merged = ConjunctiveGraph()
    # Combine all graphs for inference, preserving named graphs
    # Add quads (with context) instead of just triples
    for quad in external.quads():
        merged.add(quad)
    for quad in internal.quads():
        merged.add(quad)
    for quad in data.quads():
        merged.add(quad)
    return MergedGraph(
        data=data,
        vocab_internal=internal,
        vocab_external=external,
        merged=merged,
    )


def run_inference_backend(
    merged: MergedGraph,
    backend: str = "owlrl",
) -> None:
    """Run inference backend on merged graph using OWL-RL semantics.

    MergedGraph is updated in-place with inferred triples:
        - vocab_external_inferences: inferred triples over external vocabulary
        - full_inferences: inferred triples over all data and vocabularies

    Args:
        merged: MergedGraph containing data and vocabulary graphs.
        backend: The inference backend to use (currently only 'owlrl' is supported).

    Returns: None
        (alters input MergedGraph in place)

    Raises:
        ValueError: If backend is not 'owlrl'.

    """
    if backend != "owlrl":
        msg = f"Unsupported inference backend: {backend}. Only 'owlrl' is supported."
        raise ValueError(msg)

    closure = DeductiveClosure(OWLRL_Semantics)

    merged.vocab_external_inferences = ConjunctiveGraph(
        store=merged.vocab_external.store,
    )
    # Run OWL-RL deductive closure just over external vocabulary
    closure.expand(
        merged.vocab_external,
        destination=merged.vocab_external_inferences,
    )

    merged.full_inferences = ConjunctiveGraph(store=merged.merged.store)
    # Run OWL-RL deductive closure over everything
    closure.expand(merged.merged, destination=merged.full_inferences)
