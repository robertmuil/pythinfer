#!/usr/bin/env python3
"""Script to merge TTL files and execute inference."""

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from owlrl import DeductiveClosure
from owlrl.OWLRL import OWLRL_Semantics
from rdflib import OWL, RDF, RDFS, Dataset, Graph, IdentifiedNode, Literal, Node
from rdflib.query import ResultRow

from pythinfer.data import Query
from pythinfer.merge import IRI_EXTERNAL_INFERENCES, IRI_FULL_INFERENCES
from pythinfer.rdflibplus import DatasetView

DEF_MAX_REASONING_ROUNDS = 5
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
    DeductiveClosure(OWLRL_Semantics).expand(graph, destination_graph)  # pyright: ignore[reportUnknownMemberType]
    ntriples_inferred = len(destination_graph)

    nremoved, _ = filter_triples(destination_graph, filterset_invalid_triples)

    info("  Original triples:       %d", ntriples_orig)
    info("  Inferences, raw:        %d", ntriples_inferred)
    info("  Invalid inferences:     %d", nremoved)


###
# The following are triple-based filter functions.
# All must except Node,Node,Node because that is what rdflib provides when iterating
# over a graph. The package does not prevent use of types that are invalid in RDF.
###
_FilterFunction = Callable[[Node, Node, Node], bool]


def _subject_is_literal(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Identify when the subject is a Literal, which is invalid in RDF.

    Likely related to at least this: https://github.com/RDFLib/OWL-RL/issues/50
    """
    return isinstance(s, Literal)


def _object_is_empty_string(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Empty strings would usually be better represented as missing values."""
    return isinstance(o, Literal) and str(o) == ""


def _redundant_reflexives(s: Node, p: Node, o: Node) -> bool:
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


def _redundant_thing_declarations(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Identify useless declarations that `s` is a owl:Thing or a subclass of it."""
    return (o == OWL.Thing) and (
        p in {RDF.type, RDFS.subClassOf, RDFS.domain, RDFS.range}
    )


def _redundant_nothing_subclass(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Identify useless declarations owl:Nothing is a subclass of something."""
    return (s == OWL.Nothing) and (p == RDFS.subClassOf)


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
        filter_functions (list[Callable[[Triple], bool]]): List of functions that
            take a triple and return True if the triple should be removed.

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
            if filter_func(s, p, o):
                to_remove.append((s, p, o))
                removal_counts[filter_func] += 1

    info(
        "%d filters identified %d triples for removal:",
        len(filter_functions),
        sum(removal_counts.values()),
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

    g_external_inferences = ds.graph(IRI_EXTERNAL_INFERENCES)
    apply_owlrl_inference(external_view, g_external_inferences)

    info("  External inferences generated: %d triples", len(g_external_inferences))
    return g_external_inferences


def _run_inference_iteration(
    ds: Dataset,
    g_full_inferences: Graph,
    sparql_queries: list[Query],
    iteration: int,
) -> tuple[int, int]:
    """Run one iteration of inference (steps 3-4).

    Args:
        ds: Dataset containing all graphs.
        g_full_inferences: Graph to accumulate inferences into.
        sparql_queries: List of SPARQL CONSTRUCT queries for heuristics.
        iteration: Current iteration number (for logging).

    Returns:
        Tuple of (triples_added_owl, triples_added_sparql).

    """
    info("--- Iteration %d ---", iteration)

    # Step 3: Generate full inferences over current state
    info("  Step 3: Running OWL-RL inference over current state...")
    triples_before_owl = len(g_full_inferences)
    apply_owlrl_inference(ds, g_full_inferences)
    triples_added_owl = len(g_full_inferences) - triples_before_owl
    info("    OWL-RL added %d new inferences", triples_added_owl)

    # Step 4: Run heuristics (SPARQL CONSTRUCT queries)
    if sparql_queries:
        info("  Step 4: Running %d SPARQL heuristics...", len(sparql_queries))
        triples_before_sparql = len(g_full_inferences)

        # Apply SPARQL constructs over the entire dataset (which now includes
        # the full inferences from step 3)
        heuristic_results = apply_manual_sparql_inference(ds, sparql_queries)

        # Add heuristic results to full inferences
        for s, p, o in heuristic_results:
            g_full_inferences.add((s, p, o))

        triples_added_sparql = len(g_full_inferences) - triples_before_sparql
        info("    SPARQL heuristics added %d new inferences", triples_added_sparql)
    else:
        triples_added_sparql = 0
        info("  Step 4: No SPARQL heuristics to run")

    return triples_added_owl, triples_added_sparql


def run_inference_backend(
    ds: Dataset,
    external_graph_ids: list[IdentifiedNode],
    backend: str = "owlrl",
    max_iterations: int = DEF_MAX_REASONING_ROUNDS,
    sparql_queries: list[Query] | None = None,
) -> list[IdentifiedNode]:
    """Run inference backend on merged graph using OWL-RL semantics.

    Implements the inference process described in README.md:
    1. Load and merge (already done - ds contains merged data)
    2. Generate external inferences (once - baseline noise from external vocabs)
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
        backend: The inference backend to use (currently only 'owlrl' is supported).
        max_iterations: Maximum number of inference iterations (default 5).
        sparql_queries: Optional list of SPARQL CONSTRUCT queries for heuristics.

    Returns:
        List of all external graph identifiers (input external_graph_ids plus
        IRI_EXTERNAL_INFERENCES).

    Raises:
        ValueError: If backend is not 'owlrl'.

    """
    if backend != "owlrl":
        msg = f"Unsupported inference backend: {backend}. Only 'owlrl' is supported."
        raise ValueError(msg)

    if sparql_queries is None:
        sparql_queries = []

    # Step 2: Generate external inferences (once - this is the "noise floor")
    g_external_inferences = _generate_external_inferences(ds, external_graph_ids)

    # Steps 3-5: Iterate full inferences + heuristics until convergence
    info(
        "Steps 3-5: Iterating full inferences + heuristics (max %d iterations)...",
        max_iterations,
    )

    g_full_inferences = ds.graph(IRI_FULL_INFERENCES)
    iteration = 0
    previous_triple_count = len(ds)  # Count triples in entire dataset

    while iteration < max_iterations:
        iteration += 1

        triples_added_owl, triples_added_sparql = _run_inference_iteration(
            ds, g_full_inferences, sparql_queries, iteration
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

    if iteration >= max_iterations:
        info("  Maximum iterations (%d) reached", max_iterations)

    info("Total inferences after iteration: %d triples", len(g_full_inferences))

    # Step 6: Subtract external inferences from full inferences
    info("Step 6: Subtracting external inferences from full inferences...")
    triples_before_subtraction = len(g_full_inferences)

    for s, p, o in g_external_inferences:
        g_full_inferences.remove((s, p, o))

    triples_removed = triples_before_subtraction - len(g_full_inferences)
    info("  Removed %d external inferences", triples_removed)

    # Step 7: Subtract unwanted inferences
    info("Step 7: Filtering unwanted inferences...")
    nremoved, filter_counts = filter_triples(g_full_inferences, filterset_all)
    info("  Removed %d unwanted inferences:", nremoved)
    for filter_func, count in filter_counts.items():
        info("    - %s: %d triples", filter_func.__name__, count)

    info("Final inference graph: %d triples", len(g_full_inferences))

    # Return all external graph IDs (originals plus external inferences)
    return [
        *external_graph_ids,
        IRI_EXTERNAL_INFERENCES,
    ]
