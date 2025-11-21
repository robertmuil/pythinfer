"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from dataclasses import dataclass
from enum import Enum

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Dataset, Graph, IdentifiedNode, URIRef

from pythinfer.infer import filter_triples, filterset_all, filterset_invalid_triples
from pythinfer.inout import Project

logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug


def graph_lengths(ds: Dataset) -> dict[IdentifiedNode, int]:
    """Get lengths of all named graphs in a Dataset."""
    lengths: dict[IdentifiedNode, int] = {}
    for g in ds.graphs():
        lengths[g.identifier] = len(g)
    return lengths


# NB: in the below we are using the file *name* only as the named graph identifier.
# This assumes that input files have unique names even if in different directories,
# which is likely an invalid assumption...


class GraphCategory(Enum):
    """Categories for named graphs in the dataset."""

    DATA = "data"
    INT_VOCAB = "internal_vocab"
    EXT_VOCAB = "external_vocab"
    INF_EXT_VOCAB = "external_inferences"
    INF_FULL = "full_inferences"


@dataclass
class CategorisedDataset:
    """A container for a Dataset with an associated category for every graph.

    Attributes:
        ds: The combined Dataset containing all named graphs.
        category: Map from graph identifier to GraphCategory.

    """

    ds: Dataset
    category: dict[IdentifiedNode, GraphCategory]

    @property
    def full(self) -> Dataset:
        """Get the full inferred graph (original merged graphs plus inferences).

        Inferred triples are expected to be stored with category INF_FULL.
        """
        _full = Dataset()
        for s, p, o, c in self.ds.quads():
            # Add all quads except external vocab inferences (those are temporary)
            if c is not None:
                cat = self.category.get(c)
                if cat != GraphCategory.INF_EXT_VOCAB:
                    g = _full.graph(c)
                    g.add((s, p, o))
        return _full

    @property
    def final(self) -> Dataset:
        """Get the final graph: everything except external vocab and their inferences.

        Returns the merged input triples and full inferences, excluding:
        - External vocabulary graphs (EXT_VOCAB)
        - External vocabulary inferences (INF_EXT_VOCAB)
        """
        _final = Dataset()
        for s, p, o, c in self.ds.quads():
            if c is not None:
                cat = self.category.get(c)
                if cat not in (GraphCategory.EXT_VOCAB, GraphCategory.INF_EXT_VOCAB):
                    g = _final.graph(c)
                    g.add((s, p, o))
        return _final


def merge_graphs(
    cfg: Project,
) -> CategorisedDataset:
    """Merge graphs: preserve named graphs for each input and categorise by type.

    Loads all input files into a single Dataset with named graphs, and maintains
    a mapping from each graph identifier to its category (external vocab, internal
    vocab, or data).

    Returns:
        CategorisedDataset with all graphs merged and categorised.

    """
    merged = Dataset()
    category: dict[IdentifiedNode, GraphCategory] = {}

    # Load external vocabulary files
    for src in cfg.paths_vocab_ext:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[g.identifier] = GraphCategory.EXT_VOCAB

    # Load internal vocabulary files
    for src in cfg.paths_vocab_int:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[g.identifier] = GraphCategory.INT_VOCAB

    # Load data files
    for src in cfg.paths_data:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[g.identifier] = GraphCategory.DATA

    return CategorisedDataset(ds=merged, category=category)


def run_inference_backend(
    categorised: CategorisedDataset,
    backend: str = "owlrl",
) -> None:
    """Run inference backend on merged graph using OWL-RL semantics.

    CategorisedDataset is updated in-place with inferred triples:
        - Graphs with category INF_EXT_VOCAB: inferred triples over external vocab
        - Graphs with category INF_FULL: inferred triples over all data and vocabs

    Args:
        categorised: CategorisedDataset containing data and vocabulary graphs.
        backend: The inference backend to use (currently only 'owlrl' is supported).

    Raises:
        ValueError: If backend is not 'owlrl'.

    """
    if backend != "owlrl":
        msg = f"Unsupported inference backend: {backend}. Only 'owlrl' is supported."
        raise ValueError(msg)

    closure = DeductiveClosure(OWLRL_Semantics)

    # Run OWL-RL deductive closure just over external vocabulary
    external_vocab_ids = [
        gid
        for gid, cat in categorised.category.items()
        if cat == GraphCategory.EXT_VOCAB
    ]

    external_inf_id: URIRef = URIRef("inferences_external")  # type: ignore[bad-assignment]
    full_inf_id: URIRef = URIRef("inferences_full")  # type: ignore[bad-assignment]
    # Create a temporary dataset with just external vocab
    external_only = Graph()

    # TODO: consider using DatasetView with default_union=True instead of copying.
    for gid in external_vocab_ids:
        external_only += categorised.ds.graph(gid)

    categorised.category[external_inf_id] = GraphCategory.INF_EXT_VOCAB
    # Run inference and capture inferred triples
    inf_ext_vocab = Graph(store=external_only.store)
    closure.expand(external_only, destination=inf_ext_vocab)

    nremoved, _filter_count = filter_triples(
        inf_ext_vocab, filterset_invalid_triples
    )
    dbg(f"Removed {nremoved} invalid triples from external inferences.")


    # Seems odd there's no more direct way to add a new graph...
    # Could use the ds.graph in the expand call, but it must share store
    # with the input - which would mean copying input triples inside the ds.
    # Really not sure which is superior.
    g = categorised.ds.graph(external_inf_id)
    for s, p, o in inf_ext_vocab:
        g.add((s, p, o))

    # Run OWL-RL deductive closure over everything
    # Here we don't need to copy because we are expanding into a new graph inside
    # the same Dataset, so same backing store.
    inf_full = categorised.ds.graph(full_inf_id)  # Graph(store=categorised.ds.store)
    closure.expand(categorised.ds, destination=inf_full)
    categorised.category[full_inf_id] = GraphCategory.INF_FULL


    nremoved, _filter_count = filter_triples(inf_full, filterset_all)
    dbg(f"Removed {nremoved} invalid and unwanted triples from full inferences.")


    # Now remove all external vocab triples from the full inferences
    for gid in external_vocab_ids:
        ext_graph = categorised.ds.graph(gid)
        for s, p, o in ext_graph:
            inf_full.remove((s, p, o))
    # And all triples inferred over external vocab
    if external_vocab_ids:
        ext_inf_graph = categorised.ds.graph(external_inf_id)
        for s, p, o in ext_inf_graph:
            inf_full.remove((s, p, o))

