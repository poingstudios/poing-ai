import shutil
import tempfile
import unittest
from pathlib import Path
from poing_reviewer.engines.detector import detect_engine
from poing_reviewer.engines.godot import GodotAnalyzer
from poing_reviewer.engines.unity import UnityAnalyzer
from poing_reviewer.engines.unreal import UnrealAnalyzer
from poing_reviewer.engines.generic import GenericAnalyzer


class TestEngineDetector(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_detect_explicit(self):
        self.assertIsInstance(detect_engine(explicit_engine="godot"), GodotAnalyzer)
        self.assertIsInstance(detect_engine(explicit_engine="unity"), UnityAnalyzer)
        self.assertIsInstance(detect_engine(explicit_engine="unreal"), UnrealAnalyzer)
        self.assertIsInstance(detect_engine(explicit_engine="generic"), GenericAnalyzer)

    def test_detect_godot(self):
        (self.test_dir / "project.godot").write_text("", encoding="utf-8")
        engine = detect_engine(root_dir=self.test_dir)
        self.assertIsInstance(engine, GodotAnalyzer)

    def test_detect_unity(self):
        ps_dir = self.test_dir / "ProjectSettings"
        ps_dir.mkdir()
        (ps_dir / "ProjectSettings.asset").write_text("", encoding="utf-8")
        engine = detect_engine(root_dir=self.test_dir)
        self.assertIsInstance(engine, UnityAnalyzer)

    def test_detect_unreal(self):
        (self.test_dir / "MyGame.uproject").write_text("{}", encoding="utf-8")
        engine = detect_engine(root_dir=self.test_dir)
        self.assertIsInstance(engine, UnrealAnalyzer)


if __name__ == "__main__":
    unittest.main()
