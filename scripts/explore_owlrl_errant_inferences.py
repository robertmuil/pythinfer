"""Exploration script to demonstrate unwanted and invalid inferences by owlrl."""
# ruff: noqa: T201, INP001
import owlrl
from rdflib import Graph

g1 = Graph()
g2 = Graph(store=g1.store)

owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(g1, destination=g2)

print("First, show the unwanted triples from owlrl when given 0 triples at all:")
print(f"===g1:\n{g1.serialize()}")
print(f"===g2:\n{g2.serialize()}")
