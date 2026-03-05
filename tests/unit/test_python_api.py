"""Tests for the Python API."""

from pathlib import Path

from pythinfer.project import ProjectSpec


class TestProjectInstantiation:
    """Test various ways to instantiate Project."""

    def test_direct_instantiation(self) -> None:
        """Test that we can directly instantiate."""
        proj = ProjectSpec(name="test123", focus=[Path("blah.ttl")])
        assert proj.name == "test123"
        assert proj.path_self.stem == "generated_by_code"
        assert proj.path_self.suffix == ".nonexistent"



