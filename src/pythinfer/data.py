"""Takes care of finding and loading files, and saving data back to disk."""
# TODO: merge into inout.py
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from rdflib import Graph

logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug

SCRIPT_DIR = Path(__file__).parent
UNNECESSARY_INFERENCES_FILE = SCRIPT_DIR / "known_unecessary_inferences.ttl"

def load_graphs(input_files: list[Path]) -> Graph:
    """Load and merge multiple RDF files into a single graph.

    TODO: merge with inout functionality - likely this can just be deleted.

    Args:
        input_files: List of TTL file paths to merge

    Returns:
        Graph: Merged RDF graph

    """
    # Create a new graph
    merged_graph = Graph()

    # Parse and merge each input file
    prev_ntriples = 0
    for file_path in input_files:
        dbg("  Loading: %s", file_path)
        try:
            merged_graph.parse(file_path, format="turtle")
            ntriples = len(merged_graph)
            new_ntriples = ntriples - prev_ntriples
            prev_ntriples = ntriples
            dbg("    ✓ Successfully loaded %d new triples", new_ntriples)
        except Exception:
            logger.exception("    ✗ Error loading %s", file_path)
            continue

    return merged_graph

def load_unnecessary_inferences() -> Graph:
    """Load unnecessary inferences from preconfigured location."""
    known_unnecessary = Graph()
    known_unnecessary.parse(UNNECESSARY_INFERENCES_FILE)
    return known_unnecessary


@dataclass
class Query:
    """Represents a query string more meaningfully than str."""

    source: Path
    content: str  # Should use Template or t-string

    def __len__(self)-> int:
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
    queries = []
    for query_file in query_files:
        with query_file.open() as f:
            q = Query(source=query_file, content=f.read())
            queries.append(q)
    return queries


def save_graph(
    graph: Graph,
    output_file: Path,
    namespaces: dict[str, str] | None = None,
) -> Graph:
    """Save graph to a file. Use this to keep formatting identical.

    NB: canon longTurtle is not great with the way it orders things, so
    we might need to call out to riot unfortunately.

    Args:
        graph: RDF graph to save
        output_file: Path to save the graph
        namespaces: Optional dict of prefix->namespace bindings to apply before saving

    """
    if namespaces:
        for prefix, namespace in namespaces.items():
            graph.bind(prefix, namespace)
    return graph.serialize(destination=output_file, format="longturtle", canon=True)
