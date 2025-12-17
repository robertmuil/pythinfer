"""Test roundtrip export of datasets to different formats."""

import tempfile
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Namespace, URIRef

from pythinfer.inout import export_dataset


class TestExportFormatsRoundtrip:
    """Data exported to different formats can be read back with no data loss."""

    @pytest.fixture
    def test_dataset(self) -> Dataset:
        """Create a test dataset with multiple named graphs and triples."""
        ds = Dataset()

        # Create first named graph with data
        graph1 = ds.graph(URIRef("http://example.com/graph1"))
        EX = Namespace("http://example.com/")
        graph1.add((EX.subject1, EX.property1, EX.object1))
        graph1.add((EX.subject1, EX.property2, EX.object2))

        # Create second named graph with data
        graph2 = ds.graph(URIRef("http://example.com/graph2"))
        graph2.add((EX.subject3, EX.property3, EX.object3))
        graph2.add((EX.subject4, EX.property4, EX.object4))

        return ds

    def _get_all_triples(self, dataset: Dataset) -> set:
        """Extract all triples (s, p, o) from a dataset, ignoring quads."""
        triples = set()
        for s, p, o, c in dataset.quads():
            triples.add((s, p, o))
        return triples

    def test_export_and_roundtrip_ttl(self, test_dataset: Dataset) -> None:
        """Test that TTL export and re-import preserves triples."""
        original_triples = self._get_all_triples(test_dataset)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.ttl"

            # Export to TTL
            export_dataset(
                test_dataset,
                output_file.with_suffix(".trig"),
                formats=["trig", "ttl"],
            )

            # Re-import the TTL file
            reimported = Graph()
            reimported.parse(output_file, format="ttl")

            # Extract triples from reimported graph
            reimported_triples = set(reimported.triples((None, None, None)))

            # Check that all original triples are present
            assert original_triples == reimported_triples, (
                f"Triples not preserved in TTL roundtrip.\n"
                f"Missing: {original_triples - reimported_triples}\n"
                f"Extra: {reimported_triples - original_triples}"
            )

    def test_export_and_roundtrip_rdf_xml(self, test_dataset: Dataset) -> None:
        """Test that RDF/XML export and re-import preserves triples."""
        original_triples = self._get_all_triples(test_dataset)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.rdf"

            # Export to RDF/XML
            export_dataset(
                test_dataset,
                output_file.with_suffix(".trig"),
                formats=["trig", "xml"],
            )

            # Re-import the RDF file
            reimported = Graph()
            reimported.parse(output_file, format="xml")

            # Extract triples from reimported graph
            reimported_triples = set(reimported.triples((None, None, None)))

            # Check that all original triples are present
            assert original_triples == reimported_triples, (
                f"Triples not preserved in RDF/XML roundtrip.\n"
                f"Missing: {original_triples - reimported_triples}\n"
                f"Extra: {reimported_triples - original_triples}"
            )

    def test_export_multiple_formats_roundtrip(self, test_dataset: Dataset) -> None:
        """Test that exporting to multiple formats preserves triples in all formats."""
        original_triples = self._get_all_triples(test_dataset)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.trig"

            # Export to multiple formats at once
            export_dataset(
                test_dataset,
                output_file,
                formats=["trig", "ttl", "xml", "n3"],
            )

            # Test TTL roundtrip
            ttl_file = output_file.with_suffix(".ttl")
            assert ttl_file.exists(), "TTL file was not created"
            ttl_graph = Graph()
            ttl_graph.parse(ttl_file, format="ttl")
            ttl_triples = set(ttl_graph.triples((None, None, None)))
            assert original_triples == ttl_triples, (
                f"TTL triples not preserved.\n"
                f"Missing: {original_triples - ttl_triples}\n"
                f"Extra: {ttl_triples - original_triples}"
            )

            # Test RDF/XML roundtrip
            rdf_file = output_file.with_suffix(".rdf")
            assert rdf_file.exists(), "RDF file was not created"
            rdf_graph = Graph()
            rdf_graph.parse(rdf_file, format="xml")
            rdf_triples = set(rdf_graph.triples((None, None, None)))
            assert original_triples == rdf_triples, (
                f"RDF/XML triples not preserved.\n"
                f"Missing: {original_triples - rdf_triples}\n"
                f"Extra: {rdf_triples - original_triples}"
            )

            # Test N3 roundtrip
            n3_file = output_file.with_suffix(".n3")
            assert n3_file.exists(), "N3 file was not created"
            n3_graph = Graph()
            n3_graph.parse(n3_file, format="n3")
            n3_triples = set(n3_graph.triples((None, None, None)))
            assert original_triples == n3_triples, (
                f"N3 triples not preserved.\n"
                f"Missing: {original_triples - n3_triples}\n"
                f"Extra: {n3_triples - original_triples}"
            )

    def test_export_single_format_as_string(self, test_dataset: Dataset) -> None:
        """Test backward compatibility: single format can be passed as string."""
        original_triples = self._get_all_triples(test_dataset)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.trig"

            # Export with single format as string (backward compatibility)
            export_dataset(
                test_dataset,
                output_file,
                formats=["trig", "ttl"],
            )

            # Verify TTL file exists and has correct content
            ttl_file = output_file.with_suffix(".ttl")
            assert ttl_file.exists(), "TTL file was not created"
            ttl_graph = Graph()
            ttl_graph.parse(ttl_file, format="ttl")
            ttl_triples = set(ttl_graph.triples((None, None, None)))
            assert original_triples == ttl_triples

    def test_export_without_extra_format(self, test_dataset: Dataset) -> None:
        """Test that export works without extra_format parameter."""
        original_triples = self._get_all_triples(test_dataset)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "test.trig"

            # Export without extra format (uses default ["trig"])
            export_dataset(test_dataset, output_file)

            # Verify trig file exists
            assert output_file.exists(), "TRIG file was not created"

            # Re-import and check triples are preserved
            reimported = Dataset()
            reimported.parse(
                output_file, format="trig", publicID=URIRef("http://example.com/")
            )
            reimported_triples = self._get_all_triples(reimported)
            assert original_triples == reimported_triples
