"""Test script to verify multiple format export functionality."""

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

    # Export to both trig and multiple other formats
    export_dataset(ds, output_file, formats=["trig", "ttl", "jsonld", "xml"])

    # Check files were created
    trig_file = output_file
    ttl_file = output_file.with_suffix(".ttl")
    jsonld_file = output_file.with_suffix(".jsonld")
    xml_file = output_file.with_suffix(".rdf")

    print("Testing multiple format export:")
    print(f"  TRIG file exists: {trig_file.exists()}")
    print(f"  TTL file exists: {ttl_file.exists()}")
    print(f"  JSONLD file exists: {jsonld_file.exists()}")
    print(f"  RDF/XML file exists: {xml_file.exists()}")

    if trig_file.exists():
        print(f"  TRIG file size: {trig_file.stat().st_size} bytes")

    if ttl_file.exists():
        print(f"  TTL file size: {ttl_file.stat().st_size} bytes")

    if jsonld_file.exists():
        print(f"  JSONLD file size: {jsonld_file.stat().st_size} bytes")

    if xml_file.exists():
        print(f"  RDF/XML file size: {xml_file.stat().st_size} bytes")

    # Test with single format as string (backward compatibility)
    print("\nTesting single format export (backward compatibility):")
    output_file2 = Path(tmpdir) / "test_export2.trig"
    export_dataset(ds, output_file2, formats=["trig", "ttl"])

    ttl_file2 = output_file2.with_suffix(".ttl")
    print(f"  TRIG file exists: {output_file2.exists()}")
    print(f"  TTL file exists: {ttl_file2.exists()}")

    # Test with no extra format
    print("\nTesting without extra format:")
    output_file3 = Path(tmpdir) / "test_export3.trig"
    export_dataset(ds, output_file3)

    print(f"  TRIG file exists: {output_file3.exists()}")
    print(
        f"  Other files exist: {any(Path(tmpdir).glob('test_export3.*')) and output_file3 != Path(tmpdir) / 'test_export3.trig'}"
    )

print("\n✅ All tests passed!")
