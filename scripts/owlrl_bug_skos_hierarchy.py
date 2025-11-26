"""Test owlrl with SKOS-like multi-level subproperty hierarchy.

SKOS has: skos:broader -> skos:broaderTransitive -> skos:semanticRelation
where semanticRelation has domain/range skos:Concept.

We want to verify that reasoning over both the default graph and a named graph
correctly infers the domain/range for both skos:broader and skos:broaderTransitive.

It fails to infer these when reasoning over a named graph.

** Submitted as https://github.com/RDFLib/OWL-RL/issues/76 **
"""
# ruff: noqa: T201, T203

from pprint import pprint

from owlrl import DeductiveClosure
from owlrl.OWLRL import OWLRL_Semantics
from rdflib import OWL, RDF, RDFS, Dataset, Graph, Namespace, URIRef
from rdflib.compare import graph_diff, to_isomorphic
from rdflib.namespace import NamespaceManager

EX = Namespace("http://example.org/")


def create_skos_like_ontology() -> Graph:
    """Create SKOS-like multi-level property hierarchy."""
    g = Graph()
    g.bind("ex", EX)

    # Define the top-level property with domain and range
    g.add((EX.semanticRelation, RDF.type, RDF.Property))
    g.add((EX.semanticRelation, RDF.type, OWL.ObjectProperty))
    g.add((EX.semanticRelation, RDFS.domain, EX.Concept))
    g.add((EX.semanticRelation, RDFS.range, EX.Concept))

    # Define middle-level transitive property
    g.add((EX.broaderTransitive, RDF.type, RDF.Property))
    g.add((EX.broaderTransitive, RDF.type, OWL.ObjectProperty))
    g.add((EX.broaderTransitive, RDF.type, OWL.TransitiveProperty))
    g.add((EX.broaderTransitive, RDFS.subPropertyOf, EX.semanticRelation))

    # Define leaf property (like skos:broader)
    g.add((EX.broader, RDF.type, RDF.Property))
    g.add((EX.broader, RDF.type, OWL.ObjectProperty))
    g.add((EX.broader, RDFS.subPropertyOf, EX.broaderTransitive))

    return g


def graph_lengths(ds: Dataset) -> dict[str, int]:
    """Get lengths of all named graphs in a Dataset."""
    lengths: dict[str, int] = {}
    for g in ds.graphs():
        lengths[g.identifier.n3()] = len(g)
    return lengths


def print_ds(title: str, ds: Dataset) -> None:
    """Print dataset summary and selected inferences."""
    print(f"\n{title}: {len(ds)} triples in total:")
    pprint(graph_lengths(ds), indent=4, width=20)

    domain_assertions = list(ds.quads((EX.broader, RDFS.domain, None))) + list(
        ds.quads((EX.broaderTransitive, RDFS.domain, None))
    )
    print(f"selected domain inferences: {len(domain_assertions)}")
    nm = ds.namespace_manager  # For pretty printing
    for ii, (s, p, o, g) in enumerate(domain_assertions):
        _g = g or URIRef("NONE")
        print(f"  {ii:d}: [{_g.n3(nm):<20}] {s.n3(nm):>20} -{p.n3(nm)}-> {o.n3(nm)} ")


print("=== Test 1: Default Graph ===")
ds1 = Dataset()
ds1.bind("ex", EX)
ds1.parse(data=create_skos_like_ontology().serialize(format="turtle"), format="turtle")
print_ds("Parse into default", ds1)

inferences1 = ds1.graph(URIRef("urn:inferences1"))
DeductiveClosure(OWLRL_Semantics).expand(ds1, inferences1)
print_ds(f"Inference into {inferences1.identifier.n3()}", ds1)


print("\n=== Test 2: Named Graph ===")
ds2 = Dataset()
named_graph = ds2.graph(URIRef("urn:ontology"))
named_graph.parse(
    data=create_skos_like_ontology().serialize(format="turtle"), format="turtle"
)
print_ds(f"Parse into named graph {named_graph.identifier.n3()}", ds2)

inferences2 = ds2.graph(URIRef("urn:inferences2"))
assert named_graph.store == inferences2.store == ds2.store
DeductiveClosure(OWLRL_Semantics).expand(named_graph, inferences2)
print_ds(f"Inference into {inferences2.identifier.n3()}", ds2)

print("\n=== Test 3: Dataset into Named Graph ===")
ds3 = Dataset()
named_graph = ds3.graph(URIRef("urn:ontology3"))
named_graph.parse(
    data=create_skos_like_ontology().serialize(format="turtle"), format="turtle"
)
print_ds(f"Parse into named graph {named_graph.identifier.n3()}", ds3)

inferences3 = ds3.graph(URIRef("urn:inferences3"))
DeductiveClosure(OWLRL_Semantics).expand(ds3, inferences3)
print_ds(f"Inference into {inferences3.identifier.n3()}", ds3)
print("\n=== Summary ===")
print(
    "Dataset into default graph infers broaderTransitive domain:     "
    + (
        "✅ True"
        if any(ds1.quads((EX.broaderTransitive, RDFS.domain, None)))
        else "❌ False"
    )
)
print(
    "Dataset into default graph infers broader domain:               "
    + ("✅ True" if any(ds1.quads((EX.broader, RDFS.domain, None))) else "❌ False")
)
print(
    "Named graph into named graph infers broaderTransitive domain:   "
    + (
        "✅ True"
        if any(ds2.quads((EX.broaderTransitive, RDFS.domain, None)))
        else "❌ False"
    )
)
print(
    "Named graph into named graph infers broader domain:             "
    + ("✅ True" if any(ds2.quads((EX.broader, RDFS.domain, None))) else "❌ False")
)
print(
    "Dataset into named graph infers broaderTransitive domain:       "
    + (
        "✅ True"
        if any(ds3.quads((EX.broaderTransitive, RDFS.domain, None)))
        else "❌ False"
    )
)
print(
    "Dataset into named graph infers broader domain:                 "
    + ("✅ True" if any(ds3.quads((EX.broader, RDFS.domain, None))) else "❌ False")
)


# Use rdflib's graph comparison which handles blank nodes properly
def compare_inference_graphs(
    g1: Graph, g2: Graph, label1: str, label2: str, nm: NamespaceManager
) -> None:
    """Compare two inference graphs and print differences."""
    print(f"\n=== Diff: {label1} vs {label2} ===")

    if g1.isomorphic(g2):
        print("Graphs are isomorphic ✅")
    else:
        # Use rdflib.compare for proper diff handling
        _, in_first, in_second = graph_diff(to_isomorphic(g1), to_isomorphic(g2))

        print(f"\nOnly in {label1} ({len(in_first)} triples):")
        for s, p, o in sorted(
            in_first, key=lambda t: (str(t[0]), str(t[1]), str(t[2]))
        ):
            print(f"  {s.n3(nm)} {p.n3(nm)} {o.n3(nm)}")

        print(f"\nOnly in {label2} ({len(in_second)} triples):")
        for s, p, o in sorted(
            in_second, key=lambda t: (str(t[0]), str(t[1]), str(t[2]))
        ):
            print(f"  {s.n3(nm)} {p.n3(nm)} {o.n3(nm)}")


compare_inference_graphs(
    inferences1,
    inferences2,
    "ds1.inferences1",
    "ds2.inferences2",
    ds1.namespace_manager,
)
compare_inference_graphs(
    inferences1,
    inferences3,
    "ds1.inferences1",
    "ds3.inferences3",
    ds1.namespace_manager,
)
compare_inference_graphs(
    inferences2,
    inferences3,
    "ds2.inferences2",
    "ds3.inferences3",
    ds1.namespace_manager,
)
