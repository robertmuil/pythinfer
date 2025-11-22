"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from dataclasses import dataclass
from enum import Enum

from rdflib import Dataset, IdentifiedNode, URIRef

from pythinfer.infer import (
    apply_owlrl_inference,
    filter_triples,
    filterset_all,
)
from pythinfer.inout import Project

IRI_EXTERNAL_MERGED: URIRef = URIRef("merged_external")  # type: ignore[bad-assignment]
IRI_EXTERNAL_INFERENCES: URIRef = URIRef("inferences_external")  # type: ignore[bad-assignment]
IRI_FULL_INFERENCES: URIRef = URIRef("inferences_full")  # type: ignore[bad-assignment]

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

    ###
    # Step 1: run inference over everything
    ###

    g_full_inferences = categorised.ds.graph(IRI_FULL_INFERENCES)
    if GraphCategory.INF_FULL not in categorised.category:
        categorised.category[GraphCategory.INF_FULL] = []
    categorised.category[GraphCategory.INF_FULL].append(IRI_FULL_INFERENCES)
    apply_owlrl_inference(categorised.ds, g_full_inferences)  # pyright: ignore[reportUnknownMemberType]

    nremoved, _filter_count = filter_triples(g_full_inferences, filterset_all)
    info(
        "   Removed %d unwanted triples from full inferences:\n %s.",
        nremoved,
        _filter_count,
    )

    ###
    # Step 2: run inference over just the external vocabularies
    # Do this to remove external inferences from the full inferences, and do it
    # *after* full inference just for efficiency, so that full inference does not
    # have to process the redundant 'merged_external' graph.
    ###

    external_vocab_ids = categorised.category.get(GraphCategory.EXT_VOCAB, [])

    # Need to merge into a single graph for owlrl processing
    # TODO: consider using DatasetView with default_union=True instead of copying.
    g_external = categorised.ds.graph(IRI_EXTERNAL_MERGED)
    for gid in external_vocab_ids:
        g_external += categorised.ds.graph(gid)

    g_external_inferences = categorised.ds.graph(IRI_EXTERNAL_INFERENCES)
    apply_owlrl_inference(g_external, g_external_inferences)

    # Add inferred external vocab triples to main dataset with category
    if GraphCategory.INF_EXT_VOCAB not in categorised.category:
        categorised.category[GraphCategory.INF_EXT_VOCAB] = []
    categorised.category[GraphCategory.INF_EXT_VOCAB].append(IRI_EXTERNAL_INFERENCES)

    ###
    # Step 3: remove external inferences from full inferences, because they are
    # not likely useful: they are useful in generating the full inferences, but not
    # likely in their own right.
    ###
    for s, p, o in g_external_inferences:
        g_full_inferences.remove((s, p, o))
