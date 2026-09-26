// MeshGate — loads a canonical GLB into Unity on top of glTFast.
// One component: path/URL → GameObject hierarchy with names from glTF,
// animations (Legacy Animation, clips by name), bounds, colliders, events.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using GLTFast;
using GLTFast.Logging;
using UnityEngine;
using UnityEngine.Events;

namespace MeshGate
{
    /// <summary>Which colliders to add to the loaded asset.</summary>
    public enum MeshGateColliders { None, Box, Mesh, MeshConvex }

    [AddComponentMenu("MeshGate/MeshGate Asset")]
    public class MeshGateAsset : MonoBehaviour
    {
        [Tooltip("Path to the .glb: relative paths resolve from StreamingAssets; absolute paths and http(s)://, file:// URLs are used as is")]
        public string source = "meshgate_demo.glb";
        public bool loadOnStart = true;

        [Header("Animation")]
        public bool autoplay = true;
        [Tooltip("Play only this clip after loading (e.g. \"shamble\"); empty = every clip when autoplay is on")]
        public string playOnLoad = "";
        [Tooltip("Load <name>.<tier>.glb next to the source when MeshGateQuality.Current is a mobile tier and the file exists")]
        public bool useQualityVariant = true;
        public bool loop = true;
        [Range(0.1f, 3f)] public float speed = 1f;

        [Header("Physics")]
        public MeshGateColliders colliders = MeshGateColliders.None;

        [Header("Events")]
        public UnityEvent<MeshGateAsset> onLoaded = new UnityEvent<MeshGateAsset>();
        public UnityEvent<string> onFailed = new UnityEvent<string>();

        /// <summary>Root of the loaded hierarchy (a child of this component's GameObject).</summary>
        public Transform Root { get; private set; }
        public bool IsLoaded => Root != null;
        public GltfImport Import { get; private set; }
        public Animation LegacyAnimation { get; private set; }
        public IReadOnlyList<string> AnimationNames => _animationNames;
        public int MeshCount { get; private set; }
        public int TriangleCount { get; private set; }
        public int MaterialCount { get; private set; }
        public int SkinnedMeshCount { get; private set; }
        public int BoneCount { get; private set; }
        /// <summary>World-space bounds of all renderers (meters).</summary>
        public Bounds Bounds { get; private set; }
        public float LoadMilliseconds { get; private set; }
        /// <summary>The file actually loaded (a quality-tier variant or the canonical source).</summary>
        public string LoadedFile { get; private set; }

        readonly Dictionary<string, Transform> _byName = new Dictionary<string, Transform>();
        readonly List<string> _animationNames = new List<string>();

        async void Start()
        {
            if (loadOnStart) await LoadAsync();
        }

        /// <summary>Load a GLB from source (or another path), replacing the current asset.</summary>
        public async Task<bool> LoadAsync(string overrideSource = null)
        {
            if (!string.IsNullOrEmpty(overrideSource)) source = overrideSource;
            Unload();

            var chosen = source;
            if (useQualityVariant && MeshGateQuality.Current != MeshGateTier.PC)
            {
                var variant = MeshGateQuality.VariantPath(source, MeshGateQuality.Current);
                var local = ResolveUri(variant);
                if (variant != source && local.IsFile && File.Exists(local.LocalPath)) chosen = variant;   // Android APK / http: canonical only
            }
            LoadedFile = Path.GetFileName(chosen);
            var uri = ResolveUri(chosen);
            var t0 = Time.realtimeSinceStartup;
            var import = new GltfImport(logger: new ConsoleLogger());
            var settings = new ImportSettings
            {
                AnimationMethod = AnimationMethod.Legacy,   // clips by name, no controller
                GenerateMipMaps = true,
                NodeNameMethod = NameImportMethod.Original,  // contract: glTF names kept as is
            };
            bool ok;
            try { ok = await import.Load(uri, settings); }
            catch (Exception e) { Fail($"{source}: {e.Message}"); return false; }
            if (!ok) { Fail($"{source}: glTFast failed to parse the file"); return false; }

            var holder = new GameObject(Path.GetFileNameWithoutExtension(source));
            holder.transform.SetParent(transform, false);
            var instantiator = new GameObjectInstantiator(import, holder.transform);
            ok = await import.InstantiateMainSceneAsync(instantiator);
            if (!ok) { Destroy(holder); Fail($"{source}: failed to instantiate the scene"); return false; }

            Import = import;
            Root = holder.transform;
            LoadMilliseconds = (Time.realtimeSinceStartup - t0) * 1000f;
            IndexHierarchy();
            SetupAnimation(instantiator.SceneInstance);
            SetupColliders();
            onLoaded.Invoke(this);
            return true;
        }

        public void Unload()
        {
            if (Root != null) Destroy(Root.gameObject);
            Import?.Dispose();
            Import = null; Root = null; LegacyAnimation = null;
            _byName.Clear(); _animationNames.Clear();
            MeshCount = TriangleCount = MaterialCount = SkinnedMeshCount = BoneCount = 0;
        }

        /// <summary>Find a node by its glTF name (e.g. "crate_lid").</summary>
        public Transform Find(string nodeName) => _byName.TryGetValue(nodeName, out var t) ? t : null;
        public IEnumerable<string> NodeNames => _byName.Keys;

        // --- animation ---------------------------------------------------------
        public void Play(string clipName = null)
        {
            if (LegacyAnimation == null) return;
            foreach (AnimationState st in LegacyAnimation)
            {
                if (clipName != null && st.name != clipName) continue;
                st.wrapMode = loop ? WrapMode.Loop : WrapMode.ClampForever;
                st.speed = speed;
                st.enabled = true; st.weight = 1f;
                LegacyAnimation.Play(st.name, PlayMode.StopSameLayer);
            }
        }
        public void Stop(string clipName = null)
        {
            if (LegacyAnimation == null) return;
            if (clipName == null) LegacyAnimation.Stop(); else LegacyAnimation.Stop(clipName);
        }
        /// <summary>Play only the given clip.</summary>
        public void Solo(string clipName) { Stop(); Play(clipName); }
        public bool IsPlaying => LegacyAnimation != null && LegacyAnimation.isPlaying;
        public void SetSpeed(float value)
        {
            speed = value;
            if (LegacyAnimation == null) return;
            foreach (AnimationState st in LegacyAnimation) st.speed = value;
        }

        // --- internals -------------------------------------------------------
        static Uri ResolveUri(string src)
        {
            if (Uri.TryCreate(src, UriKind.Absolute, out var abs) && (abs.Scheme == "http" || abs.Scheme == "https" || abs.Scheme == "file" || abs.Scheme == "jar"))
                return abs;
            if (Path.IsPathRooted(src)) return new Uri(src);
            var sa = Application.streamingAssetsPath;
            return sa.Contains("://") ? new Uri(sa + "/" + src) : new Uri(Path.Combine(sa, src));
        }

        void IndexHierarchy()
        {
            var mats = new HashSet<Material>();
            foreach (var t in Root.GetComponentsInChildren<Transform>(true))
            {
                if (t == Root) continue;
                if (!_byName.ContainsKey(t.name)) _byName[t.name] = t;
            }
            var renderers = Root.GetComponentsInChildren<Renderer>(true);
            var bounds = new Bounds();
            var first = true;
            foreach (var r in renderers)
            {
                foreach (var m in r.sharedMaterials) if (m) mats.Add(m);
                // SkinnedMeshRenderer.bounds is an estimate from the root bone; the mesh bind pose via the node matrix is more accurate
                var b = r is SkinnedMeshRenderer smr && smr.sharedMesh ? TransformBounds(smr.transform.localToWorldMatrix, smr.sharedMesh.bounds) : r.bounds;
                if (first) { bounds = b; first = false; } else bounds.Encapsulate(b);
            }
            foreach (var mf in Root.GetComponentsInChildren<MeshFilter>(true))
            {
                MeshCount++;
                var mesh = mf.sharedMesh;
                if (mesh) for (int s = 0; s < mesh.subMeshCount; s++) TriangleCount += (int)(mesh.GetIndexCount(s) / 3);
            }
            var bones = new HashSet<Transform>();
            foreach (var smr in Root.GetComponentsInChildren<SkinnedMeshRenderer>(true))
            {
                MeshCount++; SkinnedMeshCount++;
                foreach (var b in smr.bones) if (b) bones.Add(b);
                var mesh = smr.sharedMesh;
                if (mesh) for (int s = 0; s < mesh.subMeshCount; s++) TriangleCount += (int)(mesh.GetIndexCount(s) / 3);
            }
            MaterialCount = mats.Count;
            BoneCount = bones.Count;
            Bounds = bounds;
        }

        static Bounds TransformBounds(Matrix4x4 m, Bounds b)
        {
            var result = new Bounds(m.MultiplyPoint3x4(b.min), Vector3.zero);
            for (var i = 1; i < 8; i++)
            {
                var c = new Vector3((i & 1) != 0 ? b.max.x : b.min.x, (i & 2) != 0 ? b.max.y : b.min.y, (i & 4) != 0 ? b.max.z : b.min.z);
                result.Encapsulate(m.MultiplyPoint3x4(c));
            }
            return result;
        }

        void SetupAnimation(GameObjectSceneInstance instance)
        {
            LegacyAnimation = instance?.LegacyAnimation;
            if (LegacyAnimation == null) return;
            var layer = 0;
            foreach (AnimationState st in LegacyAnimation)
            {
                _animationNames.Add(st.name);
                st.layer = layer++;   // each clip on its own layer so they play simultaneously
            }
            if (!string.IsNullOrEmpty(playOnLoad) && _animationNames.Contains(playOnLoad)) Solo(playOnLoad);
            else if (autoplay) Play(); else Stop();
        }

        void SetupColliders()
        {
            switch (colliders)
            {
                case MeshGateColliders.Box:
                {
                    var box = Root.gameObject.AddComponent<BoxCollider>();
                    box.center = Root.InverseTransformPoint(Bounds.center);
                    var s = Root.lossyScale;
                    box.size = new Vector3(Bounds.size.x / s.x, Bounds.size.y / s.y, Bounds.size.z / s.z);
                    break;
                }
                case MeshGateColliders.Mesh:
                case MeshGateColliders.MeshConvex:
                    foreach (var mf in Root.GetComponentsInChildren<MeshFilter>(true))
                    {
                        var mc = mf.gameObject.AddComponent<MeshCollider>();
                        mc.sharedMesh = mf.sharedMesh;
                        mc.convex = colliders == MeshGateColliders.MeshConvex;
                    }
                    break;
            }
        }

        void Fail(string message)
        {
            Debug.LogError("MeshGate: " + message, this);
            onFailed.Invoke(message);
        }

        void OnDestroy() => Unload();
    }
}
