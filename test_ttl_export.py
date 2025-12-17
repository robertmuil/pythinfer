#!/usr/bin/env python3
"""Test Dataset vs Graph serialization to TTL."""

from rdflib import Dataset, Graph, Namespace, URIRef
import tempfile
from pathlib import Path

# Create a simple test dataset
ds = Dataset()
test_graph = ds.graph(URIRef("http://example.com/test"))

EX = Namespace("http://example.com/")
test_graph.add((EX.subject1, EX.property1, EX.object1))
test_graph.add((EX.subject2, EX.property2, EX.object2))

print("Dataset length:", len(ds))
print("Test graph length:", len(test_graph))

with tempfile.TemporaryDirectory() as tmpdir:
    # Try serializing Dataset directly to TTL
    ttl_file = Path(tmpdir) / "test.ttl"
    try:
        ds.serialize(destination=str(ttl_file), format="ttl")
        print(f"Direct Dataset TTL serialization size: {ttl_file.stat().st_size}")
        with open(ttl_file) as f:
            content = f.read()
            print("Content:", content[:200] if content else "(empty)")
    except Exception as e:
        print(f"Error serializing Dataset: {e}")

    # Try serializing Graph to TTL
    graph_file = Path(tmpdir) / "test_graph.ttl"
    try:
        # Merge all graphs into a single graph
        combined_graph = Graph()
        for graph in ds.graphs():
            combined_graph += graph

        combined_graph.serialize(destination=str(graph_file), format="ttl")
        print(f"\nCombined Graph TTL serialization size: {graph_file.stat().st_size}")
        with open(graph_file) as f:
            content = f.read()
            print("Content:", content[:200] if content else "(empty)")
    except Exception as e:
        print(f"Error with Graph: {e}")
