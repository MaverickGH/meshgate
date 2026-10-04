// MeshGate — tier showcase: every asset of a pack at every quality tier, side by side, with its triangle count.
// Rows = assets from the pack's index.json, columns = mobile-low, mobile-mid, mobile-high, pc. Each copy is scaled to
// fit its cell (display only), stands on the ground and plays its clips. Used by the GeneratedTiers scene and its test.
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using UnityEngine;

namespace MeshGate
{
    public class MeshGateTierShowcase : MonoBehaviour
    {
        [System.Serializable] class PackAsset { public string file; public string title; public string kind; }
        [System.Serializable] class PackIndex { public string title; public PackAsset[] assets; }

        [Tooltip("Pack folder: relative to StreamingAssets (packs/generated) or an absolute path")]
        public string pack = "packs/generated";
        [Tooltip("Width of one cell in meters; every copy is scaled to fit it")]
        public float cell = 2.2f;
        public bool labels = true;
        [Tooltip("Point the main camera at the whole grid once it is built")]
        public bool frameCamera = true;

        public static readonly string[] Tiers = { "mobile-low", "mobile-mid", "mobile-high", "pc" };
        public static readonly int[] Budgets = { 8000, 25000, 60000, 250000 };

        /// <summary>True once every copy has loaded (or failed).</summary>
        public bool Ready { get; private set; }
        /// <summary>asset file → triangles per tier (index as in Tiers; -1 = file missing or failed).</summary>
        public readonly Dictionary<string, int[]> Triangles = new Dictionary<string, int[]>();
        public int Failed { get; private set; }
        public string PackTitle { get; private set; }
        public int Rows { get; private set; }

        async void Start() => await Build();

        float X(int column) => -column * cell;
        float Z(int row) => -(Rows - 1 - row) * cell * 1.35f;   // extra room in front of each row for its labels

        public string ResolvePack()
        {
            if (Path.IsPathRooted(pack)) return pack;
            var sa = Path.Combine(Application.streamingAssetsPath, pack);
            if (Directory.Exists(sa)) return sa;
#if UNITY_EDITOR
            var repo = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", pack));
            if (Directory.Exists(repo)) return repo;
#endif
            return sa;
        }

        public async Task Build()
        {
            var dir = ResolvePack();
            var indexPath = Path.Combine(dir, "index.json");
            if (!File.Exists(indexPath)) { Debug.LogWarning($"MeshGate showcase: no index.json in {dir}"); Ready = true; return; }
            var index = JsonUtility.FromJson<PackIndex>(File.ReadAllText(indexPath));
            PackTitle = index.title;
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            var assets = new List<PackAsset>();
            foreach (var a in index.assets) if (a.kind != "scene") assets.Add(a);
            Rows = assets.Count;
            // Layout for a camera in front (+Z, where glTF fronts face): columns run left → right along -X, the first
            // asset is the farthest row (top of the picture), labels lie on the floor facing the camera.
            for (int c = 0; c < Tiers.Length && labels; c++)
                Label($"{Tiers[c]}\n≤ {Budgets[c]:N0} tris", new Vector3(X(c), 0.02f, Z(0) - cell * 0.75f), 0.05f, font, new Color(0.65f, 0.55f, 1f));
            var loads = new List<Task>();
            for (int r = 0; r < assets.Count; r++)
            {
                var a = assets[r];
                var tris = new int[Tiers.Length];
                Triangles[a.file] = tris;
                var z = Z(r);
                if (labels) Label((a.title ?? a.file).Replace(" — ", "\n"), new Vector3(cell * 0.55f, 0.02f, z), 0.045f, font, Color.white, TextAnchor.MiddleRight);
                for (int c = 0; c < Tiers.Length; c++)
                {
                    var file = c == Tiers.Length - 1 ? a.file : Path.GetFileNameWithoutExtension(a.file) + "." + Tiers[c] + ".glb";
                    var path = Path.Combine(dir, file);
                    tris[c] = -1;
                    if (!File.Exists(path)) continue;
                    loads.Add(Place(path, new Vector3(X(c), 0f, z), tris, c, font));
                }
            }
            await Task.WhenAll(loads);
            if (frameCamera && Camera.main) FrameCamera(Camera.main);
            Ready = true;
            Debug.Log($"MeshGate showcase: {Rows} assets × {Tiers.Length} tiers from {dir}, {Failed} failed");
        }

        /// <summary>Fit everything the showcase made (models and labels) into the camera, seen from the front and above.</summary>
        public void FrameCamera(Camera cam)
        {
            var rs = GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return;
            var b = rs[0].bounds;
            foreach (var r in rs) b.Encapsulate(r.bounds);
            var dir = new Vector3(0f, 0.92f, 0.62f).normalized;   // in front (+Z) and above
            var vfov = cam.fieldOfView * Mathf.Deg2Rad / 2f;
            var hfov = Mathf.Atan(Mathf.Tan(vfov) * Mathf.Max(cam.aspect, 0.5f));
            var ext = b.extents;
            var depthOnScreen = ext.z * dir.y + ext.y * dir.z;     // how tall the grid looks from this angle
            var dist = Mathf.Max(ext.x / Mathf.Tan(hfov), depthOnScreen / Mathf.Tan(vfov)) * 1.08f + ext.y;
            var target = b.center + new Vector3(0f, 0f, ext.z * 0.18f);   // near rows sit low in a perspective view
            cam.transform.position = target + dir * dist * 1.06f;
            cam.transform.LookAt(target);
            cam.farClipPlane = Mathf.Max(cam.farClipPlane, dist * 3f);
        }

        async Task Place(string path, Vector3 at, int[] tris, int column, Font font)
        {
            var holder = new GameObject(Path.GetFileNameWithoutExtension(path));
            holder.transform.SetParent(transform, false);
            var asset = holder.AddComponent<MeshGateAsset>();
            asset.loadOnStart = false; asset.useQualityVariant = false; asset.autoplay = true;
            if (!await asset.LoadAsync(path)) { Failed++; return; }
            tris[column] = asset.TriangleCount;
            var b = asset.Bounds;
            var size = Mathf.Max(b.size.x, b.size.y, b.size.z);
            var s = size > 0 ? cell * 0.72f / size : 1f;
            holder.transform.localScale = Vector3.one * s;
            // after scaling: bottom on the ground, footprint centred in the cell
            var centre = new Vector3(b.center.x, b.min.y, b.center.z) * s;
            holder.transform.localPosition = at - centre;
            if (labels)
            {
                var over = tris[column] > Budgets[column];
                Label($"{tris[column]:N0} tris", at + new Vector3(0f, 0.02f, cell * 0.5f), 0.045f, font,
                      over ? new Color(1f, 0.4f, 0.4f) : new Color(0.55f, 0.95f, 0.6f));
            }
        }

        void Label(string text, Vector3 at, float size, Font font, Color color, TextAnchor anchor = TextAnchor.MiddleCenter)
        {
            var go = new GameObject("label " + text);
            go.transform.SetParent(transform, false);
            go.transform.localPosition = at;
            go.transform.localRotation = Quaternion.Euler(90f, 180f, 0f);   // lying on the floor, readable from the camera in front
            var tm = go.AddComponent<TextMesh>();
            tm.text = text; tm.font = font; tm.fontSize = 64; tm.characterSize = size; tm.anchor = anchor; tm.color = color;
            go.GetComponent<MeshRenderer>().sharedMaterial = font.material;
        }
    }
}
