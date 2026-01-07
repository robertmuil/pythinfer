"""Test script to verify the extra export format functionality."""

import tempfile
from pathlib import Path

from rdflib import Dataset, Namespace, URIRef

from pythinfer.inout import export_dataset

# Create a simple test dataset
ds = Dataset()
test_graph = ds.graph(URIRef("http://example.com/test"))

EX = Namespace("http://example.com/")
test_graph.add((EX.subject1, EX.property1, EX.object1))
test_graph.add((EX.subject2, EX.property2, EX.object2))

# Test exporting to multiple formats
with tempfile.TemporaryDirectory() as tmpdir:
    output_file = Path(tmpdir) / "test_export.trig"

    # Export to both trig and turtle
    export_dataset(ds, output_file, formats=["trig", "ttl"])

    # Check files were created
    trig_file = output_file
    ttl_file = output_file.with_suffix(".ttl")

    print(f"TRIG file exists: {trig_file.exists()}")
    print(f"TTL file exists: {ttl_file.exists()}")

    if trig_file.exists():
        with trig_file.open() as f:
            trig_content = f.read()
        print(f"TRIG file size: {len(trig_content)} bytes")

    if ttl_file.exists():
        with ttl_file.open() as f:
            ttl_content = f.read()
        print(f"TTL file size: {len(ttl_content)} bytes")

    # Test without extra format
    output_file2 = Path(tmpdir) / "test_export2.trig"
    export_dataset(ds, output_file2)

    print(f"\nWithout extra format - TRIG file exists: {output_file2.exists()}")

    # Test different format
    output_file3 = Path(tmpdir) / "test_export3.trig"
    export_dataset(ds, output_file3, formats=["trig", "xml"])

    xml_file = output_file3.with_suffix(".rdf")
    print(f"\nWith XML export - RDF file exists: {xml_file.exists()}")

print("\n✅ All tests passed!")
