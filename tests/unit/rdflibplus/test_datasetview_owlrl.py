"""Test that OWL-RL reasoner works correctly with DatasetView."""

from owlrl import DeductiveClosure
from owlrl.OWLRL import OWLRL_Semantics
from rdflib import RDF, RDFS, Dataset, Namespace

from pythinfer.rdflibplus import DatasetView

EX = Namespace("http://example.org/")


def test_owlrl_inference_with_datasetview() -> None:
    """Test that OWL-RL reasoner can run inference on a DatasetView.

    This test verifies that:
    1. OWL-RL reasoner uses our overridden triples() method (not store directly)
    2. DatasetView provides union behavior without needing default_union=True
    3. Inference works correctly across multiple graphs in the view
    """
    # Create a dataset with two graphs
    ds = Dataset()

    # Graph 1: Class hierarchy
    g1 = ds.graph(EX.graph1)
    g1.add((EX.Animal, RDF.type, RDFS.Class))
    g1.add((EX.Dog, RDFS.subClassOf, EX.Animal))

    # Graph 2: Instance data
    g2 = ds.graph(EX.graph2)
    g2.add((EX.fido, RDF.type, EX.Dog))

    assert len(g1) == 2
    assert len(g2) == 1

    # Create a DatasetView with both graphs
    view = DatasetView(ds, [EX.graph1, EX.graph2])

    # Run OWL-RL inference on the view
    g_inferences = ds.graph(EX.inferences)
    DeductiveClosure(OWLRL_Semantics).expand(view, g_inferences)

    # Check that we got the expected transitive inference: fido rdf:type Animal
    # This proves that the reasoner saw both graphs (the subclass and the instance)
    expected_triple = (EX.fido, RDF.type, EX.Animal)
    assert expected_triple in g_inferences, (
        f"Expected inference {expected_triple} not found. "
        f"This suggests OWL-RL is not seeing both graphs in the view."
    )

    # Verify we got a reasonable number of inferences (should be > 1)
    assert len(g_inferences) > 1, "Expected multiple inferences from OWL-RL"


def test_owlrl_with_empty_datasetview() -> None:
    """Test that OWL-RL reasoner handles empty DatasetView correctly."""
    ds = Dataset()

    # Create an empty DatasetView
    view = DatasetView(ds, [])

    # Run OWL-RL inference on empty view
    g_inferences = ds.graph(EX.inferences)
    DeductiveClosure(OWLRL_Semantics).expand(view, g_inferences)

    # Should produce minimal or no inferences from empty input
    # (OWL-RL adds some axiom triples even for empty graphs)
    assert len(g_inferences) > 0
