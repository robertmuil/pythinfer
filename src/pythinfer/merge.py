"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from pathlib import Path

from rdflib import DCTERMS, RDF, Dataset, IdentifiedNode, Namespace, URIRef

from pythinfer.inout import MERGED_FILESTEM, Project, export_dataset
from pythinfer.rdflibplus import DatasetView

logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug

# URN namespace for pythinfer graph identifiers
# Format: urn:pythinfer:{project-name}:file:{relative-path}
#     or: urn:pythinfer:{project-name}:inferences:{type}
PYTHINFER_NS = Namespace("urn:pythinfer:")


def _create_graph_urn(project: Project, file_path: Path) -> URIRef:
    """Create a stable URN identifier for a source file's named graph.

    Uses project name and relative path to create a URN that is:
    - Stable across re-parsing
    - Portable within a project
    - Explicitly non-dereferenceable
    - Informative about the source

    Args:
        project: The pythinfer project
        file_path: Path to the source file

    Returns:
        URN for the named graph, e.g.:
        urn:pythinfer:eg0-basic:file:basic-model.ttl
    """
    rel_path = file_path.relative_to(project.path_self.parent)
    # Normalize to forward slashes and replace with colons for URN structure
    # Use colons to maintain hierarchical structure in URN
    path_str = str(rel_path).replace("\\", "/").replace("/", ":")
    return PYTHINFER_NS[f"{project.name}:file:{path_str}"]


def merge_graphs(
    project: Project,
    *,
    output: Path | bool = True,
    export_external: bool = False,
    extra_export_formats: list[str] | None = None,
) -> tuple[Dataset, list[IdentifiedNode]]:
    """Merge graphs: preserve named graphs for each input.

    Loads all input files into a single Dataset with named graphs and optionally
    persists to file.

    List of external graph ids is tracked separately for filtering during export.

    Args:
        project:    Project defining what files to merge and which are external
        output:     False for no persistence, True for default, or an explicit Path
        export_external:  whether to include external graphs when exporting
        extra_export_formats: export format(s) in addition to trig (e.g., ["ttl"])

    Returns:
        Tuple of (merged Dataset, list of external graph identifiers).

    """
    ds = Dataset()
    ds.bind("pythinfer", PYTHINFER_NS)
    ds.bind("dcterms", DCTERMS)
    external_gids: list[IdentifiedNode] = []

    # Load external vocabulary files (ephemeral - used for inference only)
    for src in project.paths_vocab_ext:
        graph_urn = _create_graph_urn(project, src)
        g = ds.graph(graph_urn)
        g.parse(src, format="turtle")

        # Add provenance metadata to the graph
        g.add((graph_urn, RDF.type, PYTHINFER_NS["SourceGraph"]))
        g.add((graph_urn, DCTERMS.source, URIRef(src.resolve().as_uri())))
        g.add((graph_urn, PYTHINFER_NS["sourceType"], PYTHINFER_NS["ExternalVocabulary"]))

        external_gids.append(g.identifier)

    # Load internal vocabulary files
    for src in project.paths_vocab_int:
        graph_urn = _create_graph_urn(project, src)
        g = ds.graph(graph_urn)
        g.parse(src, format="turtle")

        # Add provenance metadata
        g.add((graph_urn, RDF.type, PYTHINFER_NS["SourceGraph"]))
        g.add((graph_urn, DCTERMS.source, URIRef(src.resolve().as_uri())))
        g.add((graph_urn, PYTHINFER_NS["sourceType"], PYTHINFER_NS["InternalVocabulary"]))

    # Load data files
    for src in project.paths_data:
        graph_urn = _create_graph_urn(project, src)
        g = ds.graph(graph_urn)
        g.parse(src, format="turtle")

        # Add provenance metadata
        g.add((graph_urn, RDF.type, PYTHINFER_NS["SourceGraph"]))
        g.add((graph_urn, DCTERMS.source, URIRef(src.resolve().as_uri())))
        g.add((graph_urn, PYTHINFER_NS["sourceType"], PYTHINFER_NS["DataGraph"]))

    if output:
        if isinstance(output, bool):
            output_file = project.path_output / f"{MERGED_FILESTEM}.trig"
            output_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            output_file = output

        output_ds = ds if export_external else DatasetView(ds, external_gids).invert()

        export_dataset(
            output_ds,
            output_file,
            formats=["trig", *(extra_export_formats or [])],
        )

    return ds, external_gids
