"""Merge RDF graphs from config, preserving named graph URIs for each input file."""

import logging
from pathlib import Path

from rdflib import Dataset, IdentifiedNode

from pythinfer.inout import MERGED_FILESTEM, Project, export_dataset
from pythinfer.rdflibplus import DatasetView

logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug


# NB: in the below we are using the file *name* only as the named graph identifier.
# This assumes that input files have unique names even if in different directories,
# which is likely an invalid assumption...


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
    external_gids: list[IdentifiedNode] = []

    # Load external vocabulary files (ephemeral - used for inference only)
    for src in project.paths_vocab_ext:
        g = ds.graph(src.name)
        g.parse(src, format="turtle")
        external_gids.append(g.identifier)

    # Load internal vocabulary files
    for src in project.paths_vocab_int:
        g = ds.graph(src.name)
        g.parse(src, format="turtle")

    # Load data files
    for src in project.paths_data:
        g = ds.graph(src.name)
        g.parse(src, format="turtle")

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
