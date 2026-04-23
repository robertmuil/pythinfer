"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from pathlib import Path

from rdflib import DCTERMS, RDF, Dataset, IdentifiedNode, URIRef

from pythinfer.inout import export_dataset, export_provenance, is_quad_file
from pythinfer.project import MERGED_FILESTEM, PYTHINFER_NS, ProjectSpec

logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug

def merge_graphs(
    project: ProjectSpec,
    *,
    output: Path | bool = True,
    extra_export_formats: list[str] | None = None,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Merge graphs: preserve named graphs for each input.

    Loads all input files into a single Dataset with named graphs and optionally
    persists to file.

    List of external graph ids is tracked separately for filtering during export.

    Args:
        project:    Project defining what files to merge and which are external
        output:     False for no persistence, True for default, or an explicit Path
        extra_export_formats: export format(s) in addition to trig (e.g., ["ttl"])

    Returns:
        Tuple of (merged Dataset, list of external graph identifiers).

    """
    ds = Dataset()
    ds.bind("pythinfer", PYTHINFER_NS)
    ds.bind("dcterms", DCTERMS)
    external_gids: list[IdentifiedNode] = []
    g_provenance = ds.graph(project.provenance_gid)

    # Load external vocabulary files (ephemeral - used for inference only)
    for src in project.reference:
        graph_urn = project.source_file_gid(src)

        if is_quad_file(src):
            # For graph-aware formats, parse directly into dataset to
            # preserve the named graph structure from the file.
            existing_gids = {g.identifier for g in ds.graphs()}
            ds.parse(src)
            new_gids = {g.identifier for g in ds.graphs()} - existing_gids
            for gid in new_gids:
                g_provenance.add((gid, RDF.type, PYTHINFER_NS["SourceGraph"]))
                g_provenance.add((gid, DCTERMS.source, URIRef(src.resolve().as_uri())))
                external_gids.append(gid)
        else:
            g = ds.graph(graph_urn)
            g.parse(src)

            # Add provenance metadata to the graph
            g_provenance.add((graph_urn, RDF.type, PYTHINFER_NS["SourceGraph"]))
            g_provenance.add(
                (graph_urn, DCTERMS.source, URIRef(src.resolve().as_uri()))
            )

            external_gids.append(g.identifier)

    # Load data files
    for src in project.focus:
        graph_urn = project.source_file_gid(src)

        if is_quad_file(src):
            # For graph-aware formats, parse directly into dataset to
            # preserve the named graph structure from the file.
            existing_gids = {g.identifier for g in ds.graphs()}
            ds.parse(src)
            new_gids = {g.identifier for g in ds.graphs()} - existing_gids
            for gid in new_gids:
                g_provenance.add((gid, RDF.type, PYTHINFER_NS["SourceGraph"]))
                g_provenance.add((gid, DCTERMS.source, URIRef(src.resolve().as_uri())))
        else:
            g = ds.graph(graph_urn)
            g.parse(src)

            # Add provenance metadata
            g_provenance.add((graph_urn, RDF.type, PYTHINFER_NS["SourceGraph"]))
            g_provenance.add(
                (graph_urn, DCTERMS.source, URIRef(src.resolve().as_uri()))
            )

    if output:
        if isinstance(output, bool):
            output_file = project.path_output / f"{MERGED_FILESTEM}.trig"
        else:
            output_file = output

        project.persist_if_absent()

        # Export main output without provenance
        export_dataset(
            ds,
            output_file,
            formats=["trig", *(extra_export_formats or [])],
            exclude_graphs=[project.provenance_gid, *external_gids],
        )

        # Export provenance separately
        export_provenance(
            ds.graph(project.provenance_gid),
            output_file,
        )

    return ds, external_gids
