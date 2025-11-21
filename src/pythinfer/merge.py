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

    We could consider making this a subclass of Dataset, and requiring a category
    mapping for every graph added. For now, this is easier to implement (though
    harder to use).

    Attributes:
        ds: The combined Dataset containing all named graphs.
        category: Map from GraphCategory to list of graph identifiers in that category.

    """

    ds: Dataset
    category: dict[GraphCategory, list[IdentifiedNode]]

    @property
    def full(self) -> Dataset:
        """Get the full inferred graph (original merged graphs plus inferences)."""
        inf_gids = self.category.get(GraphCategory.INF_FULL, [])
        if len(inf_gids) == 0:
            msg = "Inference has not been run; no INF_FULL category present."
            raise ValueError(msg)
        return self.ds

    @property
    def final(self) -> Dataset:
        """Get the final graph: everything except external vocab and their inferences.

        Returns the merged input triples and full inferences, excluding:
        - External vocabulary graphs (EXT_VOCAB)
        - External vocabulary inferences (INF_EXT_VOCAB)
        """
        _final = Dataset()
        # Collect graph IDs to exclude
        exclude_ids = set(
            self.category.get(GraphCategory.EXT_VOCAB, [])
            + self.category.get(GraphCategory.INF_EXT_VOCAB, []),
        )
        for s, p, o, c in self.ds.quads():
            if c is not None and c not in exclude_ids:
                g = _final.graph(c)
                g.add((s, p, o))
        return _final


def merge_graphs(
    cfg: Project,
) -> CategorisedDataset:
    """Merge graphs: preserve named graphs for each input and categorise by type.

    Loads all input files into a single Dataset with named graphs, and maintains
    a mapping from each GraphCategory to the list of graph identifiers in that category.

    Returns:
        CategorisedDataset with all graphs merged and categorised.

    """
    merged = Dataset()
    category: dict[GraphCategory, list[IdentifiedNode]] = {
        GraphCategory.EXT_VOCAB: [],
        GraphCategory.INT_VOCAB: [],
        GraphCategory.DATA: [],
    }

    # Load external vocabulary files
    for src in cfg.paths_vocab_ext:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[GraphCategory.EXT_VOCAB].append(g.identifier)

    # Load internal vocabulary files
    for src in cfg.paths_vocab_int:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[GraphCategory.INT_VOCAB].append(g.identifier)

    # Load data files
    for src in cfg.paths_data:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        category[GraphCategory.DATA].append(g.identifier)

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

    external_vocab_ids = categorised.category.get(GraphCategory.EXT_VOCAB, [])
    external_inf_id: URIRef = URIRef("inferences_external")  # type: ignore[bad-assignment]
    full_inf_id: URIRef = URIRef("inferences_full")  # type: ignore[bad-assignment]
    # Run OWL-RL deductive closure over just the external vocabularies
    inf_ext_vocab = categorised.ds.graph(external_inf_id)

    # Create a temporary dataset with just external vocab
    external_only = Graph()

    # TODO: consider using DatasetView with default_union=True instead of copying.
    for gid in external_vocab_ids:
        external_only += categorised.ds.graph(gid)

    # Run inference and capture inferred triples
    closure.expand(external_only, destination=inf_ext_vocab)

    nremoved, _filter_count = filter_triples(inf_ext_vocab, filterset_invalid_triples)
    dbg(f"Removed {nremoved} invalid triples from external inferences.")

    # Add inferred external vocab triples to main dataset with category
    if GraphCategory.INF_EXT_VOCAB not in categorised.category:
        categorised.category[GraphCategory.INF_EXT_VOCAB] = []
    categorised.category[GraphCategory.INF_EXT_VOCAB].append(external_inf_id)
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
    if GraphCategory.INF_FULL not in categorised.category:
        categorised.category[GraphCategory.INF_FULL] = []
    categorised.category[GraphCategory.INF_FULL].append(full_inf_id)
    closure.expand(categorised.ds, destination=inf_full)

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

