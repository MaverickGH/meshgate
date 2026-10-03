"""TripoSR setup keeps the selected CUDA wheel and can use a Windows Python without versioned commands."""
import os
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
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
        (repo / ".git").mkdir()
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

    def test_setup_without_git_extracts_verified_pinned_source_and_can_retry(self):
        (triposr.REPO / ".git").rmdir()
        triposr.REPO.rmdir()
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr(f"TripoSR-{triposr.COMMIT}/tsr/system.py", "# source")
        payload = data.getvalue()
        with patch.object(triposr.shutil, "which", side_effect=lambda name: "uv" if name == "uv" else None), \
             patch.object(triposr.urllib.request, "urlopen", return_value=io.BytesIO(payload)) as download, \
             patch.object(triposr, "SOURCE_SHA256", hashlib.sha256(payload).hexdigest()), \
             patch.object(triposr.subprocess, "check_call"):
            self.assertEqual(triposr.setup(log=lambda _: None), 0)
            self.assertEqual(triposr.setup(log=lambda _: None), 0)
        self.assertEqual(download.call_count, 1)
        self.assertTrue((triposr.REPO / "tsr/system.py").is_file())
        self.assertEqual((triposr.REPO / ".meshgate-revision").read_text(), triposr.COMMIT)

    def test_windows_uses_cpu_without_nvidia_and_compatible_cuda_for_pascal(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(triposr.sys, "platform", "win32"):
            with patch.object(triposr.shutil, "which", return_value=None):
                self.assertEqual(triposr._torch_selection(), ("torch==2.7.1", "https://download.pytorch.org/whl/cpu"))
            with patch.object(triposr.shutil, "which", return_value="nvidia-smi"), \
                 patch.object(triposr.subprocess, "check_output", return_value="6.1, 572.70\n"):
                self.assertEqual(triposr._torch_selection(), ("torch==2.7.1", "https://download.pytorch.org/whl/cu118"))
            with patch.object(triposr.shutil, "which", return_value="nvidia-smi"), \
                 patch.object(triposr.subprocess, "check_output", return_value="12.0, 580.0\n"):
                self.assertTrue(triposr._torch_selection()[1].endswith("/cpu"))

    @unittest.skipUnless(os.name == "nt", "Windows runtime dependency")
    def test_missing_vc_runtime_explains_installation_before_downloading_models(self):
        lines = []
        with patch.object(triposr.ctypes, "WinDLL", side_effect=OSError("missing DLL")), \
             patch.object(triposr.urllib.request, "urlopen") as download:
            self.assertEqual(triposr.setup(log=lines.append), 1)
        self.assertIn("vc_redist.x64.exe", lines[0])
        download.assert_not_called()


if __name__ == "__main__":
    unittest.main()
