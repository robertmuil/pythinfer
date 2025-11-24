"""Explore how default graph is handled in rdflib.

Insights, using the default memory store of rdflib:
1. The default graph has a fixed identifier: `urn:x-rdflib:default`.
2. Iterating over the Dataset directly yields all triples across all graphs,
    with namedgraph.
3. Iterating using `triples()` yields triples *from the default graph only*.
4. Iterating using `quads()` yields all quads across all graphs, with namedgraph.
5. Setting `default_union=True` yields identical behaviour for 1, 2, and 4, but
    `triples()` now yields triples from all graphs.

NB: these behaviours will vary with different stores.

Questions:
1. Why do we need `default_union` at all, given that iterating over the Dataset directly
    already yields all triples across all graphs?
"""

# ruff: noqa: T201, S101, PLR2004, INP001
from rdflib import Dataset, Graph, Literal, Namespace, URIRef

EX = Namespace("http://example.org/")

# Create some named graphs
g1 = Graph(identifier=URIRef("http://example.org/graph1"))
g1.add((EX.subject1, EX.predicate1, Literal("object1")))

g2 = Graph(identifier=URIRef("http://example.org/graph2"))
g2.add((EX.subject2, EX.predicate2, Literal("object2")))
g2.add((EX.subject3, EX.predicate3, Literal("object3")))

g3 = Graph(identifier=URIRef("http://example.org/graph3"))
g2.add((EX.subject4, EX.predicate4, Literal("object4")))
g3.add((EX.subject5, EX.predicate5, Literal("object5")))
g3.add((EX.subject6, EX.predicate6, Literal("object6")))

ds = Dataset()
print(f"Default graph IRI before adding any graphs: {ds.default_graph.identifier}")
ds.graph(g1)
ds.graph(g2)
ds.graph(g3)
assert len(ds) == 6

# Check default graph
assert isinstance(ds.default_graph, Graph)
assert len(ds.default_graph) == 0  # Default graph is empty initially
ds.default_graph.add((EX.defaultSubject, EX.defaultPredicate, Literal("defaultObject")))
assert len(ds.default_graph) == 1
assert (
    EX.defaultSubject,
    EX.defaultPredicate,
    Literal("defaultObject"),
) in ds.default_graph
assert len(ds) == 7  # Total triples across all graphs

print("\nIterate over dataset directly:")
for ii, (s, p, o, c) in enumerate(ds):
    print(
        f"{ii}: Triple: {s.n3()}, {p.n3()}, {o.n3()}, Context: {c.n3() if c is not None else 'None'}"
    )

print("\nIterate over dataset using triples():")
for ii, (s, p, o) in enumerate(ds.triples((None, None, None))):
    print(f"{ii}: Triple: {s.n3()}, {p.n3()}, {o.n3()}")

print("\nIterate over dataset using quads():")
for ii, (s, p, o, c) in enumerate(ds.quads((None, None, None, None))):
    print(
        f"{ii}: Quad: {s.n3()}, {p.n3()}, {o.n3()}, Context: {c.n3() if c is not None else 'None'}"
    )

print(f"Default graph IRI after adding graphs: {ds.default_graph.identifier}")


# Now do it all again but with default_union=True
ds_union = Dataset(default_union=True)
ds_union.graph(g1)
ds_union.graph(g2)
ds_union.graph(g3)

assert len(ds_union.default_graph) == 0  # Default graph is empty initially
ds_union.default_graph.add(
    (EX.defaultSubject, EX.defaultPredicate, Literal("defaultObject"))
)
assert len(ds_union.default_graph) == 1

assert len(ds_union) == 7  # Total triples across all graphs, including default graph
print("\nWith default_union=True:")
print(f"Default graph IRI: {ds_union.default_graph.identifier}")
print("\nIterate over dataset directly:")
for ii, (s, p, o, c) in enumerate(ds_union):
    print(
        f"{ii}: Triple: {s.n3()}, {p.n3()}, {o.n3()}, Context: {c.n3() if c is not None else 'None'}"
    )
print("\nIterate over dataset using triples():")
for ii, (s, p, o) in enumerate(ds_union.triples((None, None, None))):
    print(f"{ii}: Triple: {s.n3()}, {p.n3()}, {o.n3()}")

print("\nIterate over dataset using quads():")
for ii, (s, p, o, c) in enumerate(ds_union.quads((None, None, None, None))):
    print(
        f"{ii}: Quad: {s.n3()}, {p.n3()}, {o.n3()}, Context: {c.n3() if c is not None else 'None'}"
    )
