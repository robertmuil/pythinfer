"""Explore how `rdflib.Dataset.graph()` handles graphs have different stores.

NB: submitted as issue here: https://github.com/robertmuil/rdflib/issues/18

Insights, using the default memory store of rdflib:
1. When `Dataset.graph()` is used to request a graph identifier which does exist but in
    a different store, an empty graph is returned.
2. When `Dataset.graph()` is used to with a full Graph object, the graph is added to
    the Dataset, with the triples being copied into the Dataset's store.


Questions:
...
"""

# ruff: noqa: T201, S101, INP001
from rdflib import Dataset, Graph, Literal, Namespace

EX = Namespace("http://example.org/")

# Step 1: create a graph, and a Dataset and check they're distinct
g1 = Graph(identifier=EX.graph1)
g1.add((EX.subject1, EX.predicate1, Literal("object1")))
assert len(g1) == 1

ds1 = Dataset()
assert len(ds1) == 0
assert g1.store != ds1.store

# Step 2: add the graph to the dataset BY IDENTIFIER
ds1_g1 = ds1.graph(g1.identifier)
print(f"{len(ds1)=}")
assert len(ds1) == 0
assert len(ds1.graph(g1.identifier)) == 0

print("*NB*: Dataset still empty because g1 added by identifier from different store.")

ds2 = Dataset()
assert len(ds2) == 0
assert g1.store != ds2.store
assert ds1.store != ds2.store


# Step 3: add the graph to the dataset BY FULL OBJECT
ds2_g1 = ds2.graph(g1)
print(f"{len(ds2)=}")
assert len(ds2) == 1
assert ds2_g1.store == ds2.store
assert ds2_g1.store != g1.store
assert (EX.subject1, EX.predicate1, Literal("object1")) in ds2_g1
print("*NB*: Dataset now has one triple because g1 was added with full object.")
