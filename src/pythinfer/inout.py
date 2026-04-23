"""Input/output utilities for pythinfer package.

This module contains I/O operations: dataset export, query loading, etc.

The Project data model and project management functions (discovery, loading,
creation) live in pythinfer.project. They are re-exported here for backward
compatibility.
"""
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rdflib import Dataset, Graph, IdentifiedNode

from pythinfer.rdflibplus import DatasetView, reduce

logger = logging.getLogger(__name__)

FORMAT_TO_EXT = {
        "ttl": "ttl",
        "turtle": "ttl",
        "xml": "rdf",
        "rdfxml": "rdf",
        "n3": "n3",
        "nt": "nt",
        "nq": "nquads",
        "nquads": "nquads",
        "ntriples": "nt",
        "trig": "trig",
        "trix": "trix",
        "jsonld": "json-ld",
        "json-ld": "json-ld",
    }

QUAD_EXTENSIONS = frozenset({".trig", ".trix", ".nq", ".nquads"})

def is_quad_file(path: Path) -> bool:
    """Return True if the file extension indicates a quad-aware (graph-aware) format."""
    return path.suffix.lower() in QUAD_EXTENSIONS

def export_dataset(
    dataset: Dataset,
    output_file: Path,
    formats: list[str] | None = None,
    exclude_graphs: Sequence[IdentifiedNode] = (),
) -> None:
    """Export a Dataset or Graph to file(s) in specified format(s).

    Exports to one or more formats. For each format, the output file path stem
    is used with the appropriate file extension determined by the format.

    For non-quad-aware formats, the Dataset is merged into a single Graph before export,
    while trig/trix/nquads formats natively support multiple named graphs.

    Args:
        dataset: The Dataset or Graph object to export
        output_file: Path template for output files (determines base name and directory)
        formats: List of export formats (default: ["trig"]).
                Examples: ["trig"], ["ttl"], ["ttl", "xml", "n3"], etc.
        exclude_graphs: Graph identifiers to exclude from export (default: none).
                If provided, only graphs NOT in this list will be exported.

    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Filter dataset if exclude_graphs is provided
    if exclude_graphs:
        dataset = DatasetView(dataset, exclude_graphs).invert()

    # Determine file extension based on format
    exts = [FORMAT_TO_EXT.get(f.lower(), f.lower()) for f in (formats or ["trig"])]

    combined_graph = None
    for ext in exts:
        fmt_output_file = output_file.with_suffix(f".{ext}")

        if ext in ("trig", "trix", "nquads"):
            # For quad-aware formats (trig etc.) use Dataset directly...
            dataset.serialize(destination=str(fmt_output_file), format=ext, canon=True)
        else:
            # ...otherwise reduce Dataset first into a single Graph (only do it once)
            if combined_graph is None:
                combined_graph = reduce(dataset)
            _fmt = ext if (ext != "rdf") else "xml"
            combined_graph.serialize(
                destination=str(fmt_output_file), format=_fmt, canon=True
            )

        logger.info("Exported %d triples to %s", len(dataset), fmt_output_file)


def export_provenance(
    g: Graph,
    main_file: Path,
    formats: Sequence[str] = ["ttl"],
) -> None:
    """Export the provenance graph based on the file path of the main export.

    Provenance is expected to always accompany a main export. It is exported separately
    to avoid surprising consumers with extra triples in the main export which are not
    part of the original input data nor can be inferred from it.

    Args:
        g: The Graph to export provenance from
        main_file: Path template for output files (determines base name and directory)
        formats: List of export formats (default: ["ttl"]).
                Examples: ["trig"], ["ttl"], ["ttl", "xml", "n3"], etc.

    """
    main_file.parent.mkdir(parents=True, exist_ok=True)

    exts = [FORMAT_TO_EXT.get(f.lower(), f.lower()) for f in formats]
    for ext in exts:
        provenance_file = main_file.with_stem(
            f"{main_file.stem}-provenance"
        ).with_suffix("." + ext)
        g.serialize(destination=str(provenance_file), format=ext, canon=True)

        logger.info("Exported %d triples of provenance to %s", len(g), provenance_file)


@dataclass
class Query:
    """Represents a query string more meaningfully than str."""

    source: Path
    content: str  # Should use Template or t-string

    def __len__(self) -> int:
        """Return the length of the query string."""
        return len(self.content)

    def __str__(self) -> str:
        """Return the query contents."""
        return self.content

    @property
    def name(self) -> str:
        """Return the stem of the source path as the 'name' of the query."""
        return self.source.stem


def load_sparql_inference_queries(query_files: Sequence[Path]) -> list[Query]:
    """Load SPARQL inference queries from files.

    Returns:
        list[str]: List of SPARQL queries

    """
    queries: list[Query] = []
    for query_file in query_files:
        with query_file.open() as f:
            q = Query(source=query_file, content=f.read())
            queries.append(q)
    return queries

