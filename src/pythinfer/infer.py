#!/usr/bin/env python3
"""Script to merge TTL files and execute inference."""

import logging
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import owlrl
from rdflib import OWL, RDF, RDFS, Graph, Literal, Node
from rdflib.query import ResultRow

from pythinfer.data import Query, load_sparql_inference_queries

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


def apply_owl_inference(graph: Graph) -> Graph:
    """Apply OWL2 RL inference rules using the Owlrl library.

    TODO: can we bring anything useful from here into our merge.py inference?

    This function performs complete OWL 2 RL reasoning, which includes:
    - RDFS inference (subclass, subproperty, domain, range)
    - OWL inference (inverse properties, symmetric/transitive properties,
      property chains, equivalence, disjointness, etc.)

    Args:
        graph: RDF graph to apply reasoning to

    Returns:
        Graph: new graph including only the inferred triples

    """
    ntriples_orig = len(graph)
    info("  Starting OWL reasoning on graph with %d triples", ntriples_orig)

    # Create a copy of the graph to avoid modifying the input
    # Add and remove a triple to force different backing store... is there a better way?
    inferred_graph = Graph(store=graph.store)

    # Apply OWL 2 RL reasoning - this will add inferred triples to inferred_graph
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(graph, inferred_graph)
    ntriples_inferred = len(inferred_graph)

    # Add the two together and count because they may overlap... but this is
    # not efficient...
    g_combined = graph + inferred_graph
    ntriples_final = len(g_combined)
    info("  Original triples:       %d", ntriples_orig)
    info("  Inferred triples:       %d", ntriples_inferred)
    info("  Final triples:          %d", ntriples_final)

    return inferred_graph

###
# The following are triple-based filter functions.
# All must except Node,Node,Node because that is what rdflib provides when iterating
# over a graph. The package does not prevent use of types that are invalid in RDF.
###
def _subject_is_literal(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Identify when the subject is a Literal, which is invalid in RDF.

    Likely related to at least this: https://github.com/RDFLib/OWL-RL/issues/50
    """
    return isinstance(s, Literal)

def _object_is_empty_string(s: Node, p: Node, o: Node) -> bool:  # noqa: ARG001
    """Empty strings would usually be better represented as missing values."""
    return (isinstance(o, Literal) and str(o) == "")

def _reflexive_sameas(s: Node, p: Node, o: Node) -> bool:
    """Reflexive owl:sameAs statements are redundant and useless."""
    return ((p == OWL.sameAs) and (s == o))

def _reflexive_equivalentclass(s: Node, p: Node, o: Node) -> bool:
    """Reflexive owl:equivalentClass statements are redundant and useless."""
    return ((p == OWL.equivalentClass) and (s == o))

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
def _redundant_thing_declarations(s: Node, p: Node, o: Node) -> bool:
    """Identify useless declarations that `s` is a owl:Thing or a subclass of it."""
    return (o == OWL.Thing) and (p in {RDF.type, RDFS.subClassOf})


# Filterset for invalid RDF triples, which are logically but not syntactically valid.
# This can occur when the reasoner encounters malformed data or makes invalid
# inferences.
filterset_invalid_triples: list[Callable[[Node, Node, Node], bool]] = [
    _subject_is_literal
]
# Filterset for unwanted triples that bloat the graph but are not invalid.
filterset_unwanted_triples: list[Callable[[Node, Node, Node], bool]] = [
    _object_is_empty_string,
    _redundant_reflexives,
    _redundant_thing_declarations,
]
# Combined filterset
filterset_all: list[Callable[[Node, Node, Node], bool]] = (
    filterset_invalid_triples + filterset_unwanted_triples
)

def filter_triples(
    graph: Graph, filter_functions: list[Callable[[Node, Node, Node], bool]]
) -> tuple[int, dict[Callable[[Node, Node, Node], bool], int]]:
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
    to_remove = []
    removal_counts: defaultdict[Callable, int] = defaultdict(int)
    for s, p, o in graph:
        for filter_func in filter_functions:
            if filter_func(s, p, o):
                to_remove.append((s, p, o))
                removal_counts[filter_func] += 1

    logger.info(
        "%d filters identified %d triples for removal:",
        len(filter_functions),
        sum(removal_counts.values()),
    )
    if to_remove:
        for func, count in removal_counts.items():
            logger.info("  - %d triples identified by %s", count, func.__name__)
        for triple in to_remove:
            graph.remove(triple)

    nremoved = norig - len(graph)
    if nremoved > 0:
        logger.info("%d triples removed from graph", nremoved)
    return nremoved, removal_counts

def apply_all_inference(
    original_graph: Graph,
    sparql_queries: list[Query],
    max_rounds: int = DEF_MAX_REASONING_ROUNDS,
) -> Graph:
    """Apply all inference methods to the graph.

    This includes SPARQL-based inference, and OWL reasoning.
    Will continue to apply rounds of inference until no new triples are inferred, or
    the maximum number of rounds is reached.

    Args:
        original_graph: RDF graph to apply reasoning to
        sparql_queries: The set of queries to execute
        max_rounds: Maximum number of reasoning rounds to perform

    Returns:
        Graph: New graph with all inferred triples

    """
    nrounds = 0
    info("Applying OWL inference, round %d...", nrounds)
    inferences = apply_owl_inference(original_graph)
    info("OWL inference added %d triples", len(inferences))
    g_new = original_graph + inferences

    while nrounds < max_rounds:
        info("Applying manual SPARQL inference, round %d...", nrounds)
        inferences = apply_manual_sparql_inference(g_new, sparql_queries)
        nprior = len(g_new)
        g_new = g_new + inferences
        nadded_sparql = len(g_new) - nprior
        info(
            "SPARQL inference added %d new triples (generated %d)",
            nadded_sparql,
            len(inferences)
        )
        nrounds += 1

        info("Applying OWL inference, round %d...", nrounds)
        inferences = apply_owl_inference(g_new)
        info("OWL inference added %d new triples", len(inferences))
        g_new = g_new + inferences

        if len(g_new) - nprior == 0:
            info("No new triples inferred in this round. Stopping inference.")
            break

    # Now we remove a bunch of declarations that owlrl adds that bloat the graph, like
    # stating that rdf:HTML is a Datatype.
    # The following are not necessary if we remove external model triples later.
    # info("Discovering unnecessary declarations...")
    # known_unnecessary = load_unnecessary_inferences()
    # assert len(known_unnecessary) > 0, "No known unnecessary inferences loaded!"
    # datatype_triples = []
    # for s, p, o in g_new:
    #     if not isinstance(s, URIRef):
    #         continue
    #     ns, _local = split_uri(s)
    #     if (ns in {OWL._NS, RDFS._NS, RDF._NS, XSD._NS}) and (p == RDF.type) and o in {
    #         RDFS.Datatype, OWL.AnnotationProperty
    #     }:
    #         datatype_triples.append((s, p, o))
    #     if (s, p, o) in known_unnecessary:
    #         datatype_triples.append((s, p, o))

    # info(
    #     "  Removing %d unnecessary datatype/property declarations...",
    #     len(datatype_triples),
    # )
    # for triple in datatype_triples:
    #     g_new.remove(triple)


    info("Graph now contains %d triples", len(g_new))

    return g_new


