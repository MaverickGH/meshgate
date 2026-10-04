// MeshGate — editor utilities: validate a GLB against the contract via core/validate_glb.py.
using System.Diagnostics;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace MeshGate.Editor
{
    public static class MeshGateMenu
    {
        const string ValidatorRelative = "core/validate_glb.py";

        /// <summary>Searches upward from the project for the MeshGate repository root (by core/validate_glb.py).</summary>
        public static string FindRepoRoot()
        {
            var dir = new DirectoryInfo(Application.dataPath);
            for (var i = 0; i < 6 && dir != null; i++, dir = dir.Parent)
                if (File.Exists(Path.Combine(dir.FullName, ValidatorRelative))) return dir.FullName;
            return null;
        }

        [MenuItem("MeshGate/Validate Selected GLB")]
        public static void ValidateSelected()
        {
            var path = AssetDatabase.GetAssetPath(Selection.activeObject);
            if (string.IsNullOrEmpty(path) || !path.EndsWith(".glb"))
            {
                EditorUtility.DisplayDialog("MeshGate", "Select a .glb in the Project window.", "OK");
                return;
            }
            var report = Validate(Path.GetFullPath(path));
            Debug.Log(report);
            EditorUtility.DisplayDialog("MeshGate — Validator", report, "OK");
        }

        [MenuItem("MeshGate/Set Up Humanoid (Selected FBX)")]
        public static void SetupHumanoidSelected()
        {
            var path = AssetDatabase.GetAssetPath(Selection.activeObject);
            if (string.IsNullOrEmpty(path) || !path.ToLowerInvariant().EndsWith(".fbx"))
            {
                EditorUtility.DisplayDialog("MeshGate", "Select a character .fbx exported by MeshGate in the Project window.", "OK");
                return;
            }
            MeshGateDemoScene.ExtractFbxTextures(path, Path.ChangeExtension(path, null) + "_textures");
            MeshGateDemoScene.SetupHumanoid(path);
            var avatar = AssetDatabase.LoadAllAssetsAtPath(path).OfType<Avatar>().FirstOrDefault();
            var msg = avatar && avatar.isHuman ? $"{Path.GetFileName(path)}: Humanoid avatar is valid — clips retarget between characters."
                                               : $"{Path.GetFileName(path)}: the avatar did not map as Humanoid — check the bone names (MeshGate contract).";
            Debug.Log("MeshGate: " + msg);
            EditorUtility.DisplayDialog("MeshGate — Humanoid", msg, "OK");
        }

        /// <summary>Runs the Python validator; returns the text report (or the reason it could not run).</summary>
        public static string Validate(string glbFullPath, bool strict = false)
        {
            var root = FindRepoRoot();
            if (root == null) return "MeshGate: no repository with core/validate_glb.py found near the project — run the validator manually.";
            var psi = new ProcessStartInfo
            {
                FileName = "python3",
                Arguments = $"\"{Path.Combine(root, ValidatorRelative)}\" \"{glbFullPath}\"" + (strict ? " --strict" : ""),
                RedirectStandardOutput = true, RedirectStandardError = true, UseShellExecute = false, CreateNoWindow = true,
                StandardOutputEncoding = System.Text.Encoding.UTF8, StandardErrorEncoding = System.Text.Encoding.UTF8,
            };
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            try
            {
                using var p = Process.Start(psi);
                var output = p.StandardOutput.ReadToEnd() + p.StandardError.ReadToEnd();
                p.WaitForExit();
                return output + $"\n(exit code {p.ExitCode})";
            }
            catch (System.Exception e)
            {
                return "MeshGate: failed to start python3: " + e.Message;
            }
        }
    }
}
