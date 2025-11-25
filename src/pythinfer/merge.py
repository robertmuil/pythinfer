"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging

from rdflib import Dataset, IdentifiedNode, URIRef

from pythinfer.inout import Project

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
