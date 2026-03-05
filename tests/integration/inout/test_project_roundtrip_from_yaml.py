"""Tests for the YAML handling."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from pythinfer.project import ProjectSpec


class TestProjectRoundtrip:
    """Test roundtripping of a Project to and from yaml."""

    def test_roundtrip_basic(self) -> None:
        """Test that we can serialize to YAML, and deserialize back."""
        proj = ProjectSpec(
            name="test123",
            focus=[Path("blah.ttl")],
            reference=[Path("vocab.ttl")],
            owl_backend="owlrl",
        )
        assert proj.name == "test123"
        assert proj.path_self.stem == "generated_by_code"
        assert proj.path_self.suffix == ".nonexistent"
        assert set(proj.focus) == {Path("blah.ttl")}
        assert set(proj.reference) == {Path("vocab.ttl")}
        assert proj.owl_backend == "owlrl"


        with NamedTemporaryFile("w+", suffix=".yaml", delete=True) as tmpfile:
            tmp_path = Path(tmpfile.name).absolute()
            tmp_folder = tmp_path.parent
            # You can use tmp_path as a temporary file path here if needed

            # Loading back from yaml will resolve relative paths to absolute paths
            # relative to the project directory which here means the temporary folder.
            # This means they won't compare equal to the original relative paths.
            # The resolving of paths to absolute on loading simplifies downstream code
            # but it complicates testing.
            # To test we resolve the original paths here first before serialisation.
            proj.focus = [tmp_folder / p.name for p in proj.focus]
            proj.reference = [tmp_folder / p.name for p in proj.reference]
            proj.to_yaml(tmp_path)
            proj2 = ProjectSpec.from_yaml(tmp_path)
        assert proj2 == proj





