// MeshGate — the parts of a split model (meshgate.py gen --split): every separate thing is its own child of the root,
// named by its colour, with its origin at the middle of its base, so it can be moved, swapped or reworked on its own.
// Menu: MeshGate → Parts of Selected Model. Batch (CI / headless check):
//   Unity -batchmode -projectPath <project> -executeMethod MeshGate.Editor.MeshGateParts.ReportFolder -meshgateFolder Assets/MeshGate/<model> -quit
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;

namespace MeshGate.Editor
{
    public static class MeshGateParts
    {
        [MenuItem("MeshGate/Parts of Selected Model")]
        public static void ReportSelected()
        {
            var path = AssetDatabase.GetAssetPath(Selection.activeObject);
            var report = string.IsNullOrEmpty(path) ? "Select a .glb or .fbx made by MeshGate in the Project window." : Report(path);
            Debug.Log(report);
            EditorUtility.DisplayDialog("MeshGate — Parts", report.Length > 1500 ? report.Substring(0, 1500) + "\n…" : report, "OK");
        }

        /// <summary>Batch mode: reports every .glb and .fbx in -meshgateFolder (default Assets/MeshGate).</summary>
        public static void ReportFolder()
        {
            var args = System.Environment.GetCommandLineArgs();
            var i = System.Array.IndexOf(args, "-meshgateFolder");
            var folder = i >= 0 && i + 1 < args.Length ? args[i + 1] : "Assets/MeshGate";
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var files = Directory.GetFiles(folder).Where(f => f.EndsWith(".glb") || f.EndsWith(".fbx")).OrderBy(f => f).ToArray();
            if (files.Length == 0) Debug.LogError($"MeshGate parts: no .glb or .fbx in {folder}");
            foreach (var f in files) Debug.Log(Report(f.Replace('\\', '/')));
        }

        /// <summary>The root's children with their place, size and whether the origin sits at the base.</summary>
        public static string Report(string assetPath)
        {
            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (!prefab) return $"MeshGate parts: {assetPath} did not import as a model (is glTFast installed for .glb?)";
            var go = (GameObject)Object.Instantiate(prefab);
            try
            {
                var root = go.transform;
                while (root.childCount == 1 && root.GetComponent<Renderer>() == null) root = root.GetChild(0);   // glTF scene / FBX wrapper
                var sb = new StringBuilder($"MeshGate parts: {assetPath} — {root.childCount} parts under \"{root.name}\"\n");
                foreach (Transform part in root)
                {
                    var rends = part.GetComponentsInChildren<Renderer>();
                    if (rends.Length == 0) { sb.AppendLine($"  {part.name}: no mesh"); continue; }
                    var b = rends[0].bounds;
                    foreach (var r in rends.Skip(1)) b.Encapsulate(r.bounds);
                    var p = part.position;
                    var atBase = Mathf.Abs(b.min.y - p.y) < 0.02f && Mathf.Abs(b.center.x - p.x) < 0.02f && Mathf.Abs(b.center.z - p.z) < 0.02f;
                    sb.AppendLine($"  {part.name}: at ({p.x:0.00}, {p.y:0.00}, {p.z:0.00}), size ({b.size.x:0.00}, {b.size.y:0.00}, {b.size.z:0.00}) m, " +
                                  $"rotation {part.localEulerAngles}, origin {(atBase ? "at its base" : "NOT at its base")}");
                }
                return sb.ToString();
            }
            finally { Object.DestroyImmediate(go); }
        }
    }
}
