#!/usr/bin/env python3
"""Script to merge TTL files and execute inference."""

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from owlrl import DeductiveClosure
from owlrl.OWLRL import OWLRL_Semantics
from rdflib import (
    OWL,
    RDF,
    RDFS,
    BNode,
    Dataset,
    Graph,
    IdentifiedNode,
    Literal,
    Node,
    URIRef,
)
from rdflib.query import ResultRow

from pythinfer.inout import (
    COMBINED_FULL_FILESTEM,
    INFERRED_WANTED_FILESTEM,
    Project,
    Query,
    export_dataset,
    load_sparql_inference_queries,
)
from pythinfer.rdflibplus import DatasetView

IRI_EXTERNAL_INFERENCES: URIRef = URIRef("inferences_external")  # type: ignore[bad-assignment]
IRI_OWL_INFERENCES: URIRef = URIRef("inferences_owl")  # type: ignore[bad-assignment]
IRI_SPARQL_INFERENCES: URIRef = URIRef("inferences_sparql")  # type: ignore[bad-assignment]

MAX_REASONING_ROUNDS = 5
SCRIPT_DIR = Path(__file__).parent
logger = logging.getLogger(__name__)
info = logger.info
dbg = debug = logger.debug


def apply_manual_sparql_inference(g: Graph, queries: list[Query]) -> Graph:
    """Apply manual SPARQL-based inference rules to the graph.

    Args:
        g: RDF graph to apply inference to
        queries: list of SPARQL CONSTRUCT queries that perform the inferences
    Returns:
        Graph: New graph with only the inferred triples

    """
    info("  Have %d queries for inference", len(queries))

    g_infer = Graph()

    # Apply each construct query to the graph
    for query in queries:
        dbg("  executing query '%s' (%d characters)", query.name, len(query))
        results = g.query(query.content)
        for row in results:
            # Add each inferred triple to the graph
            if isinstance(row, (ResultRow, bool)):
                msg = f"Non-triple result ({type(row)}) from CONSTRUCT query "
                msg += f"'{query.source}'"
                raise TypeError(msg)
            g_infer.add(row)

    return g_infer


def apply_owlrl_inference(graph: Graph, destination_graph: Graph) -> None:
    """Apply OWL2 RL inference rules using the Owlrl library.

    NB: The destination graph must have the *same store* as the input graph. This
    is required by the `owlrl` library for some reason.

    NBB: Something in here sets the Dataset default_union to True, if one of the graphs
    comes from a Dataset.

    This function performs complete OWL 2 RL reasoning, which includes:
    - RDFS inference (subclass, subproperty, domain, range)
    - OWL inference (inverse properties, symmetric/transitive properties,
      property chains, equivalence, disjointness, etc.)

    Args:
        graph: RDF graph to apply reasoning to
        destination_graph: Optional graph to store the inferred triples

    Returns:
        None
            (inferred triples are added to destination_graph)

    """
    ntriples_orig = len(graph)
    info(
        "  Applying OWL inference from `%s` into `%s`",
        graph.identifier,
        destination_graph.identifier,
    )
    # Apply OWL 2 RL reasoning - this will add inferred triples to destination_graph
    # WARNING - this expand() call will set Dataset.default_union = True if one or both
    # of the graphs is from a Dataset
    DeductiveClosure(OWLRL_Semantics).expand(graph, destination_graph)  # pyright: ignore[reportUnknownMemberType]
    ntriples_inferred = len(destination_graph)

    nremoved, _ = filter_triples(destination_graph, filterset_invalid_triples)

    info("  Original triples:       %d", ntriples_orig)
    info("  Inferences, raw:        %d", ntriples_inferred)
    info("  Invalid inferences:     %d", nremoved)


###
# The following are triple filter functions. Some are per-triple (they ignore the graph)
# and some are graph-based (they use the full graph to determine whether to remove a
# triple).
# All must except Node,Node,Node as the first 3 arguments because that is what rdflib
# provides when iterating over a graph.
# The package does not prevent use of types that are invalid in RDF.
# The 4th argument is the full Graph.
# All must return True if the triple is to be removed.
###
_FilterFunction = Callable[[Node, Node, Node, Graph], bool]


# Per-triple filter functions (4th argument is ignored)
def _subject_is_literal(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Identify when the subject is a Literal, which is invalid in RDF.

    Likely related to at least this: https://github.com/RDFLib/OWL-RL/issues/50
    """
    return isinstance(s, Literal)


def _object_is_empty_string(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Empty strings would usually be better represented as missing values."""
    return isinstance(o, Literal) and str(o) == ""


def _redundant_reflexives(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Reflexive statements that are redundant and useless, such as sameAs."""
    return (s == o) and (
        p
        in {
            OWL.sameAs,
            OWL.equivalentClass,
            OWL.equivalentProperty,
            RDFS.subClassOf,
            RDFS.subPropertyOf,
        }
    )


def _redundant_thing_declarations(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Identify useless declarations that `s` is a owl:Thing or a subclass of it."""
    return (o == OWL.Thing) and (
        p in {RDF.type, RDFS.subClassOf, RDFS.domain, RDFS.range}
    )


def _redundant_nothing_subclass(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Identify useless declarations owl:Nothing is a subclass of something."""
    return (s == OWL.Nothing) and (p == RDFS.subClassOf)


###
# The following are Graph-based filter functions.
# They must accept the full graph as well in order to determine whether to
# remove a given triple.
# As above, must return True if the triple is to be removed.
###


def _undeclared_blank_nodes(s: Node, p: Node, o: Node, g: Graph) -> bool:  # noqa: ARG001
    """Identify triples with blank nodes that are not declared in the graph."""
    if isinstance(o, BNode) and p in (
        RDF.type,
        RDFS.subClassOf,
        RDFS.subPropertyOf,
        RDFS.domain,
        RDFS.range,
    ):
        # Check if there is any usage of this blank node as a subject in the graph
        return not any(g.triples((o, None, None)))
    return False


# Filterset for invalid RDF triples, which are logically but not syntactically valid.
# This can occur when the reasoner encounters malformed data or makes invalid
# inferences.
filterset_invalid_triples: list[_FilterFunction] = [_subject_is_literal]
# Filterset for unwanted triples that bloat the graph but are not invalid.
filterset_unwanted_triples: list[_FilterFunction] = [
    _object_is_empty_string,
    _redundant_reflexives,
    _redundant_thing_declarations,
    _redundant_nothing_subclass,
    _undeclared_blank_nodes,
]
# Combined filterset
filterset_all: list[_FilterFunction] = (
    filterset_invalid_triples + filterset_unwanted_triples
)


def filter_triples(
    graph: Graph, filter_functions: list[_FilterFunction]
) -> tuple[int, dict[_FilterFunction, int]]:
    """Filter triples from the graph using the provided filter functions.

    ***NB: graph is modified in place.***

    Also note that the counts of triples to remove may overlap, as a triple may be
    identified for removal by multiple filter functions. Therefore, the number of
    triples actually removed will be *less than or equal to* the sum of the counts.

    Note that this deliberately does not return the graph to make clear that graph is
    modified in place.

    Args:
        graph (Graph): The RDF graph to validate and clean.
        filter_functions (list[Callable[[Triple, Graph], bool]]): List of functions that
            take a triple and a Graph and return True if the triple should be removed.

    Returns: tuple of:
        int: number of triples actually removed
        dict[Callable, int]: number of triples identified for removal by each filter

    """
    norig = len(graph)
    # Make a list of triples to remove - do not remove while iterating
    to_remove: list[tuple[Node, Node, Node]] = []
    removal_counts: defaultdict[_FilterFunction, int] = defaultdict(int)
    for s, p, o in graph:
        for filter_func in filter_functions:
            if filter_func(s, p, o, graph):
                to_remove.append((s, p, o))
                removal_counts[filter_func] += 1

    info(
        "%d triples identified for removal by %d filters:",
        sum(removal_counts.values()),
        len(filter_functions),
    )
    if to_remove:
        for func, count in removal_counts.items():
            info("  - %d triples identified by %s", count, func.__name__)
        for triple in to_remove:
            graph.remove(triple)

    nremoved = norig - len(graph)
    if nremoved > 0:
        info("%d triples removed from graph", nremoved)
    return nremoved, removal_counts


def _generate_external_inferences(
    ds: Dataset, external_graph_ids: list[IdentifiedNode]
) -> Graph:
    """Generate inferences from external vocabularies only (step 2).

    This creates the "noise floor" of inferences that come from external
    vocabularies like OWL, RDFS, SKOS, etc. These will be subtracted later.

    Args:
        ds: Dataset containing all graphs.
        external_graph_ids: List of graph identifiers that are external.

    Returns:
        Graph containing external inferences.

    """
    info("Step 2: Generating external inferences (baseline from external vocabs)...")

    # Create a DatasetView containing only external vocabularies (or empty if none).
    external_view = DatasetView(ds, external_graph_ids)

    # Workaround for owlrl bug #76: copy to temp dataset with triples in default graph
    # https://github.com/RDFLib/OWL-RL/issues/76
    info("  Creating temporary dataset to work around owlrl named graph bug...")
    temp_ds = external_view.collapse()
    info("  Temporary dataset created with %d triples in default graph", len(temp_ds))

    # Create inferences graph in temp dataset (must share same store)
    temp_inferences = temp_ds.graph(IRI_EXTERNAL_INFERENCES)

    apply_owlrl_inference(temp_ds, temp_inferences)

    g_external_inferences = ds.graph(IRI_EXTERNAL_INFERENCES)
    for s, p, o in temp_inferences:
        g_external_inferences.add((s, p, o))
    info("  External inferences generated: %d triples", len(g_external_inferences))
    return g_external_inferences


def _run_inference_iteration(
    ds: Dataset,
    g_inferences_owl: Graph,
    g_inferences_sparql: Graph,
    sparql_queries: list[Query],
    iteration: int,
) -> tuple[int, int]:
    """Run one iteration of inference (steps 3-4).

    Args:
        ds: Dataset containing all graphs.
        g_inferences_owl: Graph to accumulate OWL inferences into.
        g_inferences_sparql: Graph to accumulate SPARQL inferences into.
        sparql_queries: List of SPARQL CONSTRUCT queries for heuristics.
        iteration: Current iteration number (for logging).

    Returns:
        Tuple of (triples_added_owl, triples_added_sparql).

    """
    assert ds.store == g_inferences_owl.store, "Graphs must share the same store"
    assert ds.store == g_inferences_sparql.store, "Graphs must share the same store"

    info("--- Iteration %d ---", iteration)

    # Step 3: Generate full inferences over current state
    info("  Step 3: Running OWL-RL inference over current state...")
    triples_before_owl = len(g_inferences_owl)
    apply_owlrl_inference(ds, g_inferences_owl)
    triples_added_owl = len(g_inferences_owl) - triples_before_owl
    info("    OWL-RL added %d new inferences", triples_added_owl)

    # Step 4: Run heuristics (SPARQL CONSTRUCT queries)
    if sparql_queries:
        info("  Step 4: Running %d SPARQL heuristics...", len(sparql_queries))
        triples_before_sparql = len(g_inferences_sparql)

        # Apply SPARQL constructs over the entire dataset (which now includes
        # the full inferences from step 3)
        heuristic_results = apply_manual_sparql_inference(ds, sparql_queries)

        # Add heuristic results to full inferences
        for s, p, o in heuristic_results:
            g_inferences_sparql.add((s, p, o))

        triples_added_sparql = len(g_inferences_sparql) - triples_before_sparql
        info("    SPARQL heuristics added %d new inferences", triples_added_sparql)
    else:
        triples_added_sparql = 0
        info("  Step 4: No SPARQL heuristics to run")

    return triples_added_owl, triples_added_sparql


def run_inference_backend(
    ds: Dataset,
    external_graph_ids: list[IdentifiedNode],
    project: Project,
    output: Path | None = None,
    *,
    include_unwanted_triples: bool = False,
    export_full: bool = True,
    export_external_inferences: bool = False,
    extra_export_formats: list[str] | None = None,
) -> list[IdentifiedNode]:
    """Run inference backend on merged graph using OWL-RL semantics.

    Implements the inference process described in README.md:
    1. Load and merge (already done - ds contains merged data)
    2. Generate external inferences (do once - baseline noise from external vocabs)
    3. Generate full inferences over current state
    4. Run heuristics (SPARQL CONSTRUCT queries)
    5. Repeat steps 3-4 until convergence or max iterations
    6. Subtract external data and inferences
    7. Subtract unwanted inferences

    Dataset is updated in-place with inferred triples:
        - Graph IRI_FULL_INFERENCES: inferred triples over all data and vocabs
        - Graph IRI_EXTERNAL_INFERENCES: inferred triples over external vocab only

    Args:
        ds: Dataset containing data and vocabulary graphs.
        external_graph_ids: List of graph identifiers that are external (ephemeral).
        project: The project configuration to use (includes backend and other settings).
        output: Path to export inferences to, or None for project default
        include_unwanted_triples: If True, do not filter unwanted triples.
        export_full: export a file with the full set of inputs and inferences
            - this can be used for caching and for diagnostics
        export_external_inferences: when exporting inferences, include external graphs
        extra_export_formats: export formats in addition to trig e.g., ["ttl", "jsonld"]

    Returns:
        List of all external graph identifiers (input external_graph_ids plus
        IRI_EXTERNAL_INFERENCES).

    Raises:
        ValueError: If backend is not 'owlrl'.

    """
    if project.owl_backend != "owlrl":
        msg = (
            f"Unsupported inference backend: {project.owl_backend}. "
            "Only 'owlrl' is currently supported."
        )
        raise NotImplementedError(msg)

    sparql_queries = load_sparql_inference_queries(project.paths_sparql_inference or [])

    # Step 2: Generate external inferences (once - this is the "noise floor")
    g_external_inferences = _generate_external_inferences(ds, external_graph_ids)

    # Steps 3-5: Iterate full inferences + heuristics until convergence
    info(
        "Steps 3-5: Iterating full inferences + heuristics (max %d iterations)...",
        MAX_REASONING_ROUNDS,
    )

    g_inferences_owl = ds.graph(IRI_OWL_INFERENCES)
    g_inferences_sparql = ds.graph(IRI_SPARQL_INFERENCES)
    iteration = 0
    previous_triple_count = len(ds)  # Count triples in entire dataset

    while iteration < MAX_REASONING_ROUNDS:
        iteration += 1

        triples_added_owl, triples_added_sparql = _run_inference_iteration(
            ds, g_inferences_owl, g_inferences_sparql, sparql_queries, iteration
        )

        # Check for convergence
        current_triple_count = len(ds)
        new_triples_this_iteration = current_triple_count - previous_triple_count

        info(
            "  Total new triples this iteration: %d (OWL: %d, SPARQL: %d)",
            new_triples_this_iteration,
            triples_added_owl,
            triples_added_sparql,
        )

        if new_triples_this_iteration == 0:
            info("  Convergence reached - no new triples generated")
            break

        previous_triple_count = current_triple_count

    if iteration >= MAX_REASONING_ROUNDS:
        logger.warning("  Maximum iterations (%d) reached", MAX_REASONING_ROUNDS)

    info(
        "Total valid inferences after iteration: %d triples",
        len(g_inferences_owl) + len(g_inferences_sparql),
    )

    # Step 6: Subtract external inferences from full inferences
    # This is actually unnecessary if we are only exporting internal graphs later,
    # because the inference engine is expected not to add inferences that already exist.
    # This has been verified with `owlrl`, but not other backends yet.

    # As a matter of diagnostic, if we are in DEBUG mode, we check how many triples
    # would be removed here.
    info("Step 6: external inference subtraction implicit because of named graphs.")
    if logger.isEnabledFor(logging.DEBUG):
        dbg("%d external inferences", len(g_external_inferences))

        triples_overlapping = sum(
            1 for s, p, o in g_external_inferences if (s, p, o) in g_inferences_owl
        )

        dbg("  %d of these exist in full", triples_overlapping)

        assert triples_overlapping == 0  # noqa: S101

    if export_full:
        output_file = project.path_output / f"{COMBINED_FULL_FILESTEM}.trig"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        export_dataset(
            ds,
            output_file,
            formats=["trig", *(extra_export_formats or [])],
        )

    if not include_unwanted_triples:
        # Step 7: Subtract unwanted inferences
        info("Step 7: Filtering unwanted inferences...")
        filter_triples(g_inferences_owl, filterset_all)
        filter_triples(g_inferences_sparql, filterset_all)

    info(
        "Final inference graphs: %d triples",
        len(g_inferences_owl) + len(g_inferences_sparql),
    )

    all_external_ids: list[IdentifiedNode] = [
        *external_graph_ids,
        IRI_EXTERNAL_INFERENCES,
    ]

    output_file = output or project.path_output / f"{INFERRED_WANTED_FILESTEM}.trig"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_ds = DatasetView(
        ds,
        [IRI_OWL_INFERENCES, IRI_SPARQL_INFERENCES]
        + ([IRI_EXTERNAL_INFERENCES] if export_external_inferences else []),
    )

    export_dataset(
        output_ds,
        output_file,
        formats=["trig", *(extra_export_formats or [])],
    )

    # Return all external graph IDs (originals plus external inferences)
    return all_external_ids


def load_cache(project: Project) -> Dataset | None:
    """Load cached inferred dataset if it exists and is valid.

    Valid means that the project's input files have not changed since the cache
    was created.

    The cache file is the COMBINED_FULL file in the project's output folder.

    We set the default_union of the Dataset to True here, because the cached
    file contains named graphs. This ensures that queries over the Dataset
    will see all triples by default. It turns out that the owlrl expand() call
    does this implicitly, which is why the queries work after inference.

    Args:
        project: Project defining the paths.

    Returns:
        Dataset if cache file exists AND IS VALID, else None.

    """
    cache_file = project.path_output / f"{COMBINED_FULL_FILESTEM}.trig"
    if not cache_file.exists():
        return None

    # Check if cache is valid
    cache_mtime = cache_file.stat().st_mtime
    for path in [project.path_self, *project.paths_all]:
        if path.stat().st_mtime > cache_mtime:
            info(
                "Cache file `%s` is outdated due to updated file `%s`",
                cache_file,
                path,
            )
            return None

    # Load cached dataset
    info(f"Loading cached dataset from `{cache_file}`")
    ds = Dataset(default_union=True)
    ds.parse(str(cache_file), format="trig")
    return ds
