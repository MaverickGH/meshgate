// MeshGate — quality tiers for Unity: mobile-low / mobile-mid / mobile-high / pc.
// The table mirrors the "render" part of core/profiles.json (tests/check_profiles.py keeps them in sync).
// Apply() changes QualitySettings for the session and, on URP, a runtime copy of the pipeline asset (the project's
// asset on disk is never modified). MeshGateAsset picks <name>.<tier>.glb when Current is not PC and the file exists.
using System.Reflection;
using UnityEngine;
using UnityEngine.Rendering;

namespace MeshGate
{
    public enum MeshGateTier { Auto, MobileLow, MobileMid, MobileHigh, PC }

    [AddComponentMenu("MeshGate/MeshGate Quality")]
    [DefaultExecutionOrder(-1000)]   // before MeshGateAsset loads, so it picks the right variant
    public class MeshGateQuality : MonoBehaviour
    {
        [Tooltip("Auto = detect from the device (desktop → PC; phones by memory and cores)")]
        public MeshGateTier tier = MeshGateTier.Auto;

        public static MeshGateTier Current { get; private set; } = MeshGateTier.PC;
        public static string CurrentId => Id(Current);

        public struct Settings
        {
            public string id, label, shadows;
            public float pixelRatio, renderScale, shadowDistance, lodBias;
            public int msaa, shadowMap, textureLimit, anisotropy;
            public bool ao, bloom, hdr;
        }

        public static readonly Settings[] Table =
        {
            new Settings { id = "mobile-low", label = "Mobile · low", pixelRatio = 1.0f, renderScale = 0.75f, msaa = 0, shadows = "off", shadowMap = 0, shadowDistance = 0f, ao = false, bloom = false, hdr = false, lodBias = 0.5f, textureLimit = 1, anisotropy = 1 },
            new Settings { id = "mobile-mid", label = "Mobile · mid", pixelRatio = 1.5f, renderScale = 0.9f, msaa = 2, shadows = "hard", shadowMap = 1024, shadowDistance = 15f, ao = false, bloom = false, hdr = false, lodBias = 1.0f, textureLimit = 0, anisotropy = 2 },
            new Settings { id = "mobile-high", label = "Mobile · high", pixelRatio = 2.0f, renderScale = 1.0f, msaa = 4, shadows = "soft", shadowMap = 2048, shadowDistance = 30f, ao = false, bloom = true, hdr = true, lodBias = 1.5f, textureLimit = 0, anisotropy = 4 },
            new Settings { id = "pc", label = "PC · high quality", pixelRatio = 2.0f, renderScale = 1.0f, msaa = 4, shadows = "soft", shadowMap = 4096, shadowDistance = 80f, ao = true, bloom = true, hdr = true, lodBias = 2.0f, textureLimit = 0, anisotropy = 16 },
        };

        static RenderPipelineAsset _originalPipeline;
        static bool _pipelineSwapped;

        void Awake() => Apply(tier);

        public static string Id(MeshGateTier t) => t switch
        {
            MeshGateTier.MobileLow => "mobile-low",
            MeshGateTier.MobileMid => "mobile-mid",
            MeshGateTier.MobileHigh => "mobile-high",
            _ => "pc",
        };

        public static Settings Get(MeshGateTier t)
        {
            var id = Id(t == MeshGateTier.Auto ? Detect() : t);
            foreach (var s in Table) if (s.id == id) return s;
            return Table[Table.Length - 1];
        }

        /// <summary>Desktop/console → PC. Phones and tablets: ≤ 3.5 GB RAM or ≤ 4 cores → low, ≥ 7.5 GB and ≥ 8 cores → high, else mid.</summary>
        public static MeshGateTier Detect()
        {
            if (SystemInfo.deviceType != DeviceType.Handheld) return MeshGateTier.PC;
            var mem = SystemInfo.systemMemorySize;   // MB
            var cores = SystemInfo.processorCount;
            if (mem <= 3500 || cores <= 4) return MeshGateTier.MobileLow;
            if (mem >= 7500 && cores >= 8) return MeshGateTier.MobileHigh;
            return MeshGateTier.MobileMid;
        }

        public static void Apply(MeshGateTier t)
        {
            if (t == MeshGateTier.Auto) t = Detect();
            Current = t;
            var s = Get(t);
            QualitySettings.antiAliasing = s.msaa;
            QualitySettings.shadows = s.shadows == "off" ? ShadowQuality.Disable : s.shadows == "hard" ? ShadowQuality.HardOnly : ShadowQuality.All;
            QualitySettings.shadowResolution = s.shadowMap >= 4096 ? ShadowResolution.VeryHigh : s.shadowMap >= 2048 ? ShadowResolution.High
                                             : s.shadowMap >= 1024 ? ShadowResolution.Medium : ShadowResolution.Low;
            QualitySettings.shadowDistance = s.shadowDistance;
            QualitySettings.lodBias = s.lodBias;
            QualitySettings.globalTextureMipmapLimit = s.textureLimit;
            QualitySettings.anisotropicFiltering = s.anisotropy >= 8 ? AnisotropicFiltering.ForceEnable : s.anisotropy > 1 ? AnisotropicFiltering.Enable : AnisotropicFiltering.Disable;
            QualitySettings.skinWeights = s.id == "mobile-low" ? SkinWeights.TwoBones : SkinWeights.FourBones;
            foreach (var cam in Camera.allCameras) { cam.allowHDR = s.hdr; cam.allowMSAA = s.msaa > 0; }
            ApplyPipeline(s);
        }

        /// <summary>URP/HDRP: render scale, MSAA, shadow distance, HDR on a runtime copy of the active pipeline asset.</summary>
        static void ApplyPipeline(Settings s)
        {
            var active = QualitySettings.renderPipeline != null ? QualitySettings.renderPipeline : GraphicsSettings.defaultRenderPipeline;
            if (active == null) return;   // built-in pipeline: QualitySettings above is all there is
            if (!_pipelineSwapped)
            {
                _originalPipeline = QualitySettings.renderPipeline;
                var copy = Object.Instantiate(active);
                copy.name = active.name + " (MeshGate runtime)";
                QualitySettings.renderPipeline = copy;
                _pipelineSwapped = true;
                active = copy;
            }
            Set(active, "renderScale", s.renderScale);
            Set(active, "msaaSampleCount", Mathf.Max(1, s.msaa));
            Set(active, "shadowDistance", s.shadowDistance);
            Set(active, "supportsHDR", s.hdr);
        }

        /// <summary>Put the project's own pipeline asset back (tests, editor tools).</summary>
        public static void Restore()
        {
            if (_pipelineSwapped) { QualitySettings.renderPipeline = _originalPipeline; _pipelineSwapped = false; }
            Apply(MeshGateTier.PC);
        }

        static void Set(object target, string property, object value)
        {
            var p = target.GetType().GetProperty(property, BindingFlags.Public | BindingFlags.Instance);
            if (p != null && p.CanWrite)
            {
                try { p.SetValue(target, System.Convert.ChangeType(value, p.PropertyType)); } catch { /* property type differs between URP versions */ }
            }
        }

        /// <summary>path/asset.glb → path/asset.&lt;tier&gt;.glb</summary>
        public static string VariantPath(string source, MeshGateTier t)
        {
            var id = Id(t);
            if (id == "pc" || !source.EndsWith(".glb", System.StringComparison.OrdinalIgnoreCase)) return source;
            return source.Substring(0, source.Length - 4) + "." + id + ".glb";
        }
    }
}
