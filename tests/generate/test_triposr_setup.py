"""TripoSR setup keeps the selected CUDA wheel and can use a Windows Python without versioned commands."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "sources" / "generate"))
from mesh import triposr


class TripoSRSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = Path(self.tmp.name)
        repo = home / "TripoSR"
        repo.mkdir()
        self.python = home / "venv" / "Scripts" / "python.exe"
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        for mocked in (patch.object(triposr, "HOME", home), patch.object(triposr, "REPO", repo),
                       patch.object(triposr, "VENV", home / "venv"),
                       patch.object(triposr, "python", return_value=self.python),
                       patch.dict(os.environ, {"MESHGATE_TRIPOSR_TORCH_SPEC": "torch==2.7.1",
                                               "MESHGATE_TRIPOSR_TORCH_INDEX": "https://download.pytorch.org/whl/cu118"})):
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_cuda_wheel_uses_its_index_without_changing_other_package_sources(self):
        with patch.object(triposr.shutil, "which", side_effect=lambda name: name), \
             patch.object(triposr.subprocess, "check_call") as run, patch.object(triposr.subprocess, "call"):
            self.assertEqual(triposr.setup(log=lambda _: None), 0)
        installs = [c.args[0] for c in run.call_args_list if "install" in c.args[0]]
        self.assertIn("torch==2.7.1", installs[0])
        self.assertEqual(installs[0][-2:], ["--index-url", "https://download.pytorch.org/whl/cu118"])
        self.assertNotIn("torch", installs[1])
        self.assertNotIn("torch==2.7.1", installs[1])
        self.assertNotIn("--index-url", installs[1])
        self.assertIn("numpy<2", installs[1])

    def test_current_python_is_used_when_uv_and_versioned_python_commands_are_missing(self):
        self.python.unlink()
        with patch.object(triposr.shutil, "which", side_effect=lambda name: "git" if name == "git" else None), \
             patch.object(triposr.sys, "version_info", (3, 12, 0)), \
             patch.object(triposr.subprocess, "check_call") as run, patch.object(triposr.subprocess, "call"):
            self.assertEqual(triposr.setup(log=lambda _: None), 0)
        self.assertIn([sys.executable, "-m", "venv", str(triposr.VENV)], [c.args[0] for c in run.call_args_list])


if __name__ == "__main__":
    unittest.main()
