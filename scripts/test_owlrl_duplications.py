"""Test to confirm OWL-RL reasoner behavior with pre-existing inferences."""

import logging
from rdflib import Dataset, Graph, Namespace, RDF, RDFS
from owlrl import DeductiveClosure
from owlrl.OWLRL import OWLRL_Semantics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define a test namespace
EX = Namespace("http://example.org/")


def test_owlrl_with_preexisting_inferences_separate_graphs():
    """Test if OWL-RL generates inferences that already exist in a different graph."""
    logger.info("\n=== Test: Pre-existing inferences in separate graph ===")

    # Create a dataset with two named graphs
    ds = Dataset()

    # Graph 1: Contains base data
    g_data = ds.graph(EX.data)
    g_data.add((EX.Cat, RDFS.subClassOf, EX.Animal))
    g_data.add((EX.Animal, RDFS.subClassOf, EX.LivingThing))
    g_data.add((EX.fluffy, RDF.type, EX.Cat))

    logger.info("Initial data graph has %d triples:", len(g_data))
    for triple in g_data:
        logger.info("  %s", triple)

    # Graph 2: Pre-existing inferences (simulating what Step 2 does)
    g_preexisting = ds.graph(EX.preexisting_inferences)
    # This is what the reasoner WOULD infer from g_data
    g_preexisting.add((EX.fluffy, RDF.type, EX.Animal))  # via Cat subClassOf Animal
    g_preexisting.add((EX.Cat, RDFS.subClassOf, EX.LivingThing))  # transitive

    logger.info("Pre-existing inferences graph has %d triples:", len(g_preexisting))
    for triple in g_preexisting:
        logger.info("  %s", triple)

    # Graph 3: Destination for NEW inferences (simulating what Step 3 does)
    g_new_inferences = ds.graph(EX.new_inferences)

    logger.info("\nDataset before reasoning has %d total triples", len(ds))

    # Now run inference over the ENTIRE dataset (which includes both g_data and g_preexisting)
    # This simulates Step 3, where we reason over a dataset that already contains
    # the external inferences from Step 2
    logger.info("\nRunning OWL-RL over entire dataset into new_inferences graph...")
    DeductiveClosure(OWLRL_Semantics).expand(ds, g_new_inferences)

    logger.info("\nAfter reasoning:")
    logger.info("  Dataset total: %d triples", len(ds))
    logger.info("  Data graph: %d triples", len(g_data))
    logger.info("  Pre-existing inferences: %d triples", len(g_preexisting))
    logger.info("  NEW inferences graph: %d triples", len(g_new_inferences))

    logger.info("\nNEW inferences generated:")
    for triple in g_new_inferences:
        logger.info("  %s", triple)

    # Check if the pre-existing inferences were duplicated into new_inferences
    duplicates = []
    for s, p, o in g_preexisting:
        if (s, p, o) in g_new_inferences:
            duplicates.append((s, p, o))

    logger.info("\n=== RESULT ===")
    if duplicates:
        logger.info(
            "DUPLICATES FOUND: %d triples were in both graphs:", len(duplicates)
        )
        for triple in duplicates:
            logger.info("  %s", triple)
        logger.info(
            "Conclusion: OWL-RL DOES duplicate inferences into destination graph"
        )
    else:
        logger.info("NO DUPLICATES: Pre-existing inferences were NOT duplicated")
        logger.info(
            "Conclusion: OWL-RL does NOT duplicate inferences that already exist in input"
        )

    return len(duplicates) == 0  # True if no duplicates


def test_owlrl_with_preexisting_inferences_same_graph():
    """Test if OWL-RL generates inferences that already exist in the destination graph."""
    logger.info("\n\n=== Test: Pre-existing inferences in destination graph ===")

    # Create a simple graph with base data
    g = Graph()
    g.add((EX.Cat, RDFS.subClassOf, EX.Animal))
    g.add((EX.Animal, RDFS.subClassOf, EX.LivingThing))
    g.add((EX.fluffy, RDF.type, EX.Cat))

    logger.info("Initial graph has %d triples:", len(g))
    for triple in g:
        logger.info("  %s", triple)

    # Manually add an inference that the reasoner would normally generate
    g.add((EX.fluffy, RDF.type, EX.Animal))
    logger.info("\nManually added inference: (fluffy, type, Animal)")
    logger.info("Graph now has %d triples", len(g))

    # Now run inference - will it add the same triple again?
    logger.info("\nRunning OWL-RL over graph (destination = same graph)...")
    triples_before = len(g)
    DeductiveClosure(OWLRL_Semantics).expand(g)
    triples_after = len(g)

    logger.info("\n=== RESULT ===")
    logger.info("Triples before: %d", triples_before)
    logger.info("Triples after: %d", triples_after)
    logger.info("New triples: %d", triples_after - triples_before)

    logger.info("\nAll triples after reasoning:")
    for triple in g:
        logger.info("  %s", triple)

    # RDFlib automatically deduplicates, so we can't tell if owlrl tried to add it
    logger.info("\nNote: RDFlib graphs auto-deduplicate, so we can't detect if OWL-RL")
    logger.info("attempted to add the same triple twice")


if __name__ == "__main__":
    # Run both tests
    no_duplicates_separate = test_owlrl_with_preexisting_inferences_separate_graphs()
    test_owlrl_with_preexisting_inferences_same_graph()

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    if no_duplicates_separate:
        print(
            "✓ OWL-RL does NOT duplicate inferences from input into destination graph"
        )
        print("  This means Step 6 removing 0 triples is EXPECTED behavior!")
        print(
            "  The external inferences are already in a separate graph (IRI_EXTERNAL_INFERENCES)"
        )
        print("  and the reasoner doesn't put them into IRI_FULL_INFERENCES.")
    else:
        print(
            "✗ OWL-RL DOES duplicate inferences, so Step 6 should be removing triples"
        )
        print("  The fact that it removes 0 suggests a different problem.")
