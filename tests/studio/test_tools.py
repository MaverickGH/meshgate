"""Tool discovery regressions, without installing Blender or changing user profiles."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import meshgate


class BlenderProfileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()   # macOS: the temp folder /var/… is a link to /private/var/…
        self.exe = self.root / "Blender 4.5" / "blender.exe"
        self.exe.parent.mkdir()
        self.exe.touch()
        self.global_profile = self.root / "appdata" / "Blender Foundation" / "Blender" / "4.5"
        for mocked in (patch.object(meshgate, "blender_version", return_value="4.5.14 LTS"),
                       patch.object(meshgate.platform, "system", return_value="Windows"),
                       patch.dict(os.environ, {"APPDATA": str(self.root / "appdata")})):
            mocked.start()
            self.addCleanup(mocked.stop)

    def install_fixture(self, profile, legacy=False):
        addon = profile / ("scripts/addons/meshgate" if legacy else "extensions/user_default/meshgate")
        addon.mkdir(parents=True)
        (addon / "__init__.py").touch()
        return str(addon)

    def test_normal_windows_profile(self):
        installed = self.install_fixture(self.global_profile)
        self.assertEqual(meshgate._addon_installed(str(self.exe)), installed)

    def test_portable_profile_takes_precedence(self):
        self.install_fixture(self.global_profile)
        portable = self.install_fixture(self.exe.parent / "portable")
        self.assertEqual(meshgate._addon_installed(str(self.exe)), portable)

    def test_empty_portable_profile_does_not_use_global_addon(self):
        self.install_fixture(self.global_profile)
        (self.exe.parent / "portable").mkdir()
        self.assertIsNone(meshgate._addon_installed(str(self.exe)))

    def test_portable_legacy_addon(self):
        portable = self.install_fixture(self.exe.parent / "portable", legacy=True)
        self.assertEqual(meshgate._addon_installed(str(self.exe)), portable)


if __name__ == "__main__":
    unittest.main()
