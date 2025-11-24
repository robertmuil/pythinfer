"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from enum import Enum

from rdflib import Dataset, IdentifiedNode, URIRef

from pythinfer.infer import (
    apply_owlrl_inference,
    filter_triples,
    filterset_all,
)
from pythinfer.inout import Project
from pythinfer.rdflibplus import DatasetView

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
    """Categories for named graphs in the dataset.

    EXTERNAL: External vocabulary graphs and their inferences
              (ephemeral, not exported).
    INTERNAL: Internal vocabularies, data, and full inferences
              (exported in final output).
    """

    EXTERNAL = "external"
    INTERNAL = "internal"


def merge_graphs(
    cfg: Project,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Merge graphs: preserve named graphs for each input.

    Loads all input files into a single Dataset with named graphs.
    External vocabulary files are tracked separately for filtering during export.

    Returns:
        Tuple of (merged Dataset, list of external graph identifiers).

    """
    merged = Dataset()
    external_graph_ids: list[IdentifiedNode] = []

    # Load external vocabulary files (ephemeral - used for inference only)
    for src in cfg.paths_vocab_ext:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")
        external_graph_ids.append(g.identifier)

    # Load internal vocabulary files
    for src in cfg.paths_vocab_int:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")

    # Load data files
    for src in cfg.paths_data:
        g = merged.graph(src.name)
        g.parse(src, format="turtle")

    return merged, external_graph_ids


def create_final_dataset(
    ds: Dataset,
    external_graph_ids: list[IdentifiedNode],
) -> DatasetView:
    """Create a final dataset view excluding external graphs.

    Returns a DatasetView containing only internal graphs:
    - Internal vocabularies
    - Data files
    - Full inferences

    Excludes:
    - External vocabulary graphs
    - External inferences

    The returned view shares the same underlying store as the input Dataset,
    so no triples are copied. The view's serialize() method will only output
    the included graphs.

    Args:
        ds: The full Dataset including all graphs.
        external_graph_ids: List of graph identifiers to exclude.

    Returns:
        DatasetView with only internal (non-external) graphs.

    """
    exclude_ids = set(external_graph_ids)
    internal_graph_ids = [
        g.identifier for g in ds.graphs() if g.identifier not in exclude_ids
    ]
    return DatasetView(ds, internal_graph_ids)


def run_inference_backend(
    ds: Dataset,
    external_graph_ids: list[IdentifiedNode],
    backend: str = "owlrl",
) -> list[IdentifiedNode]:
    """Run inference backend on merged graph using OWL-RL semantics.

    Dataset is updated in-place with inferred triples:
        - Graph IRI_FULL_INFERENCES: inferred triples over all data and vocabs
        - Graph IRI_EXTERNAL_INFERENCES: inferred triples over external vocab only

    External inferences are subtracted from full inferences since they're typically
    not useful in their own right (only useful for deriving full inferences).

    Args:
        ds: Dataset containing data and vocabulary graphs.
        external_graph_ids: List of graph identifiers that are external (ephemeral).
        backend: The inference backend to use (currently only 'owlrl' is supported).

    Returns:
        List of all external graph identifiers (input external_graph_ids plus
        IRI_EXTERNAL_INFERENCES).

    Raises:
        ValueError: If backend is not 'owlrl'.

    """
    if backend != "owlrl":
        msg = f"Unsupported inference backend: {backend}. Only 'owlrl' is supported."
        raise ValueError(msg)

    ###
    # Step 1: run inference over everything
    ###

    g_full_inferences = ds.graph(IRI_FULL_INFERENCES)
    apply_owlrl_inference(ds, g_full_inferences)  # pyright: ignore[reportUnknownMemberType]

    nremoved, _filter_count = filter_triples(g_full_inferences, filterset_all)
    info(
        "   Removed %d unwanted triples from full inferences:\n %s.",
        nremoved,
        _filter_count,
    )

    ###
    # Step 2: run inference over just the external vocabularies (or an empty
    # graph if there are none) to isolate axiom inferences.
    # Do this to remove external/axiom inferences from the full inferences, and
    # do it *after* full inference just for efficiency.
    ###

    # Create a DatasetView containing only external vocabularies (or empty if none).
    # The view's triples() method provides union behavior automatically.
    external_view = DatasetView(ds, external_graph_ids)

    g_external_inferences = ds.graph(IRI_EXTERNAL_INFERENCES)
    apply_owlrl_inference(external_view, g_external_inferences)

    ###
    # Step 3: remove external/axiom inferences from full inferences, because they
    # are not likely useful: they are useful in generating the full inferences, but
    # not likely useful in their own right.
    ###
    for s, p, o in g_external_inferences:
        g_full_inferences.remove((s, p, o))

    # Return all external graph IDs (originals plus external inferences)
    return [
        *external_graph_ids,
        IRI_EXTERNAL_INFERENCES,
    ]
