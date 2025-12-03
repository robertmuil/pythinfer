#!/usr/bin/env python3
"""Test script to demonstrate Pydantic validation in Project model."""

from pathlib import Path

from pythinfer.inout import Project

print("=" * 70)
print("Testing Pydantic validation for Project model")
print("=" * 70)

# Test 1: Valid config with hyphenated keys
print("\n✅ Test 1: Valid config with hyphenated keys")
valid_config = {
    "name": "test-project",
    "path_self": Path("/tmp/test.yaml"),
    "data": ["file1.ttl", "file2.ttl"],
    "internal-vocabs": ["vocab1.ttl"],
    "external-vocabs": ["vocab2.ttl"],
    "owl-backend": "owlrl",
    "sparql-inference": ["query1.sparql"],
}
try:
    p = Project(**valid_config)
    print(f"   Success! Project name: {p.name}")
    print(f"   Data files: {len(p.paths_data)}")
    print(f"   Internal vocabs: {len(p.paths_vocab_int)}")
    print(f"   External vocabs: {len(p.paths_vocab_ext)}")
    print(f"   OWL backend: {p.owl_backend}")
    print(f"   SPARQL queries: {len(p.paths_sparql_inference)}")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 2: Valid config with underscored keys
print("\n✅ Test 2: Valid config with underscored keys")
valid_config_2 = {
    "name": "test-project-2",
    "path_self": Path("/tmp/test2.yaml"),
    "data": ["file1.ttl"],
    "internal_vocabs": ["vocab1.ttl"],
    "external_vocabs": ["vocab2.ttl"],
}
try:
    p = Project(**valid_config_2)
    print(f"   Success! Project name: {p.name}")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 3: Invalid - unexpected key
print("\n❌ Test 3: Invalid config with unexpected key (should fail)")
invalid_config = {
    "name": "test-project-3",
    "path_self": Path("/tmp/test3.yaml"),
    "data": ["file1.ttl"],
    "unexpected_field": "this should cause an error",
}
try:
    p = Project(**invalid_config)
    print("   FAILED: Should have raised validation error!")
except Exception as e:
    print(f"   Expected error caught: {type(e).__name__}")
    print(f"   Error message: {str(e).split('For further')[0].strip()}")

# Test 4: Invalid - missing required field
print("\n❌ Test 4: Invalid config missing required field (should fail)")
invalid_config_2 = {
    "name": "test-project-4",
    "path_self": Path("/tmp/test4.yaml"),
    # Missing 'data' field
}
try:
    p = Project(**invalid_config_2)
    print("   FAILED: Should have raised validation error!")
except Exception as e:
    print(f"   Expected error caught: {type(e).__name__}")
    print(f"   Missing field: paths_data")

# Test 5: Invalid - empty data list
print("\n❌ Test 5: Invalid config with empty data list (should fail)")
invalid_config_3 = {
    "name": "test-project-5",
    "path_self": Path("/tmp/test5.yaml"),
    "data": [],  # Empty list should fail min_length=1 constraint
}
try:
    p = Project(**invalid_config_3)
    print("   FAILED: Should have raised validation error!")
except Exception as e:
    print(f"   Expected error caught: {type(e).__name__}")
    print(f"   Constraint violation: min_length=1")

# Test 6: Load from actual YAML file
print("\n✅ Test 6: Load from actual YAML file (eg0-basic)")
try:
    yaml_path = Path("example_projects/eg0-basic/pythinfer.yaml")
    if yaml_path.exists():
        p = Project.from_yaml(yaml_path)
        print(f"   Success! Loaded project: {p.name}")
        print(f"   Data files: {p.paths_data}")
    else:
        print("   SKIPPED: example file not found")
except Exception as e:
    print(f"   FAILED: {e}")

# Test 7: Load YAML with hyphenated keys
print("\n✅ Test 7: Load from YAML with hyphenated keys (eg2-projects)")
try:
    yaml_path = Path("example_projects/eg2-projects/pythinfer.yaml")
    if yaml_path.exists():
        p = Project.from_yaml(yaml_path)
        print(f"   Success! Loaded project: {p.name}")
        print(f"   External vocabs: {p.paths_vocab_ext}")
    else:
        print("   SKIPPED: example file not found")
except Exception as e:
    print(f"   FAILED: {e}")

print("\n" + "=" * 70)
print("All validation tests completed!")
print("=" * 70)
