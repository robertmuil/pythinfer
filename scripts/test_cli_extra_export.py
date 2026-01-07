"""Test script to verify the CLI extra export format functionality."""

import subprocess
import tempfile
from pathlib import Path

# Use one of the example projects
example_project = Path(__file__).parent.parent / "example_projects" / "eg0-basic"

with tempfile.TemporaryDirectory() as tmpdir:
    # Copy example project to temp directory
    import shutil

    test_project = Path(tmpdir) / "test_project"
    shutil.copytree(example_project, test_project)

    # Test 1: Merge with extra export format
    print("Test 1: Testing 'merge' command with extra export format (turtle)")
    result = subprocess.run(
        ["uv", "run", "pythinfer", "merge", "-x", "ttl"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    print(f"Exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    else:
        print("✅ Merge command succeeded")

    # Check output files
    derived_dir = test_project / "derived"
    trig_file = derived_dir / "0-merged.trig"
    ttl_file = derived_dir / "0-merged.ttl"

    print(f"  TRIG file exists: {trig_file.exists()}")
    print(f"  TTL file exists: {ttl_file.exists()}")

    if trig_file.exists():
        print(f"  TRIG file size: {trig_file.stat().st_size} bytes")
    if ttl_file.exists():
        print(f"  TTL file size: {ttl_file.stat().st_size} bytes")

    # Test 2: Infer with extra export format
    print("\nTest 2: Testing 'infer' command with extra export format (jsonld)")
    result = subprocess.run(
        ["uv", "run", "pythinfer", "infer", "-x", "json-ld"],
        cwd=test_project,
        capture_output=True,
        text=True,
    )
    print(f"Exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    else:
        print("✅ Infer command succeeded")

    # Check output files
    combined_trig = derived_dir / "1-combined-full.trig"
    combined_jsonld = derived_dir / "1-combined-full.json-ld"
    inferred_trig = derived_dir / "2-inferred-wanted.trig"
    inferred_jsonld = derived_dir / "2-inferred-wanted.json-ld"

    print(f"  Combined TRIG file exists: {combined_trig.exists()}")
    print(f"  Combined JSONLD file exists: {combined_jsonld.exists()}")
    print(f"  Inferred TRIG file exists: {inferred_trig.exists()}")
    print(f"  Inferred JSONLD file exists: {inferred_jsonld.exists()}")

    if combined_jsonld.exists():
        print(f"  Combined JSONLD size: {combined_jsonld.stat().st_size} bytes")
    if inferred_jsonld.exists():
        print(f"  Inferred JSONLD size: {inferred_jsonld.stat().st_size} bytes")

    # Test 3: Infer without extra export format (should only export trig)
    print("\nTest 3: Testing 'infer' command without extra export format")
    test_project2 = Path(tmpdir) / "test_project2"
    shutil.copytree(example_project, test_project2)

    result = subprocess.run(
        ["uv", "run", "pythinfer", "infer"],
        cwd=test_project2,
        capture_output=True,
        text=True,
    )
    print(f"Exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"STDOUT:\n{result.stdout}")
        print(f"STDERR:\n{result.stderr}")
    else:
        print("✅ Infer command (without extra format) succeeded")

    derived_dir2 = test_project2 / "derived"
    jsonld_file = derived_dir2 / "2-inferred-wanted.json-ld"
    trig_file = derived_dir2 / "2-inferred-wanted.trig"

    print(f"  TRIG file exists: {trig_file.exists()}")
    print(f"  JSONLD file exists: {jsonld_file.exists()}")

    if all([trig_file.exists(), jsonld_file.exists()]):
        print("\n✅ All CLI tests passed!")
    else:
        print("\n❌ Some tests failed")
