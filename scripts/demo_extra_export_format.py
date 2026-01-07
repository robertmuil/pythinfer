"""Demonstration of the new --extra-export-format feature."""

import subprocess
import tempfile
from pathlib import Path

print("=" * 70)
print("pythinfer Extra Export Format Feature Demo")
print("=" * 70)

# Use one of the example projects
example_project = Path(__file__).parent.parent / "example_projects" / "eg0-basic"

with tempfile.TemporaryDirectory() as tmpdir:
    # Copy example project to temp directory
    import shutil

    test_project = Path(tmpdir) / "test_project"
    shutil.copytree(example_project, test_project)

    # Demo 1: merge with extra XML export
    print("\n1. Merge with --extra-export-format xml (-x xml)")
    print("-" * 70)
    result = subprocess.run(
        ["uv", "run", "pythinfer", "merge", "-x", "xml"],
        check=False,
        cwd=test_project,
        capture_output=True,
        text=True,
    )

    derived_dir = test_project / "derived"
    for f in sorted(derived_dir.glob("0-merged.*")):
        size = f.stat().st_size
        print(f"  ✓ Created {f.name:<30} ({size:>6} bytes)")

    # Demo 2: infer with extra N3 export
    print("\n2. Infer with --extra-export-format n3 (-x n3)")
    print("-" * 70)
    result = subprocess.run(
        ["uv", "run", "pythinfer", "infer", "-x", "n3"],
        check=False,
        cwd=test_project,
        capture_output=True,
        text=True,
    )

    output_files = [
        "0-merged.trig",
        "0-merged.n3",
        "1-combined-full.trig",
        "1-combined-full.n3",
        "2-inferred-wanted.trig",
        "2-inferred-wanted.n3",
    ]

    for filename in output_files:
        f = derived_dir / filename
        if f.exists():
            size = f.stat().st_size
            print(f"  ✓ {filename:<30} ({size:>6} bytes)")
        else:
            print(f"  ✗ {filename:<30} (not found)")

    # Demo 3: Show without extra export
    print("\n3. Without --extra-export-format (only trig)")
    print("-" * 70)
    test_project2 = Path(tmpdir) / "test_project2"
    shutil.copytree(example_project, test_project2)

    result = subprocess.run(
        ["uv", "run", "pythinfer", "merge"],
        check=False,
        cwd=test_project2,
        capture_output=True,
        text=True,
    )

    derived_dir2 = test_project2 / "derived"
    for f in sorted(derived_dir2.glob("0-merged.*")):
        size = f.stat().st_size
        print(f"  ✓ {f.name:<30} ({size:>6} bytes)")

print("\n" + "=" * 70)
print("Demo Summary")
print("=" * 70)
print("""
The new --extra-export-format (-x) option allows you to export to additional
formats while keeping the default trig format. This is useful for:

  • Integration with other tools that prefer specific formats
  • Creating backup copies in alternative serializations
  • Supporting downstream analysis pipelines

Usage:
  pythinfer merge -x ttl          # Export to both .trig and .ttl
  pythinfer infer -x xml          # Export to both .trig and .rdf
  pythinfer merge -x n3           # Export to both .trig and .n3

Supported formats include: ttl, turtle, xml, rdfxml, n3, nt, ntriples,
trig, trix, jsonld, json-ld

Note: Some formats may require additional dependencies (e.g., rdflib-jsonld
for JSON-LD support).
""")

print("=" * 70)
