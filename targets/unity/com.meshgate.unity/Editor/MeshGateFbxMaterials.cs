// MeshGate — materials from Blender-exported FBX (Principled BSDF → FbxSurfacePhong).
//
// Unity does not map these materials to Standard / URP Lit on its own: textures in a Blender FBX
// point to a nonexistent *.fbm folder (even though they are embedded), and metallic/roughness are stored in
// ReflectionFactor / ShininessExponent. This postprocessor reads the MaterialDescription and
// assigns everything to the active shader's slots. Textures are looked up by file name among extracted
// textures (ModelImporter.ExtractTextures) and the FBX's sub-assets.
//
// Applies to FBX files whose name contains "meshgate" or that live under Assets/MeshGate/, or to all of them if applyToAll = true.
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.AssetImporters;
using UnityEngine;

namespace MeshGate.Editor
{
    public class MeshGateFbxMaterials : AssetPostprocessor
    {
        public static bool applyToAll = false;

        public override uint GetVersion() => 2;

        void OnPreprocessMaterialDescription(MaterialDescription d, Material m, AnimationClip[] clips)
        {
            if (!assetPath.EndsWith(".fbx", System.StringComparison.OrdinalIgnoreCase)) return;
            if (!applyToAll && !Path.GetFileName(assetPath).ToLowerInvariant().Contains("meshgate")
                && !assetPath.StartsWith("Assets/MeshGate/", System.StringComparison.Ordinal)) return;

            // Base: color + albedo.
            var albedo = ResolveTexture(d, "DiffuseColor");
            if (d.TryGetProperty("DiffuseColor", out Vector4 diffuse))
                SetColor(m, albedo ? Color.white : (Color)diffuse, "_BaseColor", "_Color");   // Blender writes 0.8 when a texture is present
            if (albedo) SetTexture(m, albedo, "_BaseMap", "_MainTex");

            // Metallic (ReflectionFactor) and smoothness from ShininessExponent = (1 − roughness)² · 100.
            if (d.TryGetProperty("ReflectionFactor", out float metallic)) SetFloat(m, Mathf.Clamp01(metallic), "_Metallic");
            if (d.TryGetProperty("ShininessExponent", out float shininess))
                SetFloat(m, Mathf.Clamp01(Mathf.Sqrt(Mathf.Max(shininess, 0f) / 100f)), "_Smoothness", "_Glossiness");

            // Normals.
            var normal = ResolveTexture(d, "NormalMap") ?? ResolveTexture(d, "Bump");
            if (normal)
            {
                MarkAsNormalMap(normal);
                SetTexture(m, normal, "_BumpMap");
                m.EnableKeyword("_NORMALMAP");
            }

            // Emission.
            var emissiveTex = ResolveTexture(d, "EmissiveColor");
            d.TryGetProperty("EmissiveColor", out Vector4 emissive);
            var emissiveFactor = d.TryGetProperty("EmissiveFactor", out float ef) ? ef : 1f;
            var emissiveColor = (Color)emissive * emissiveFactor;
            if (emissiveTex || emissiveColor.maxColorComponent > 0.001f)
            {
                SetColor(m, emissiveTex ? Color.white * emissiveFactor : emissiveColor, "_EmissionColor");
                if (emissiveTex) SetTexture(m, emissiveTex, "_EmissionMap");
                m.EnableKeyword("_EMISSION");
                m.globalIlluminationFlags = MaterialGlobalIlluminationFlags.RealtimeEmissive;
            }
        }

        // --- texture lookup --------------------------------------------------------
        Texture ResolveTexture(MaterialDescription d, string property)
        {
            if (!d.TryGetProperty(property, out TexturePropertyDescription t)) return null;
            if (t.texture) return t.texture;
            var name = Path.GetFileNameWithoutExtension(string.IsNullOrEmpty(t.relativePath) ? t.path : t.relativePath);
            if (string.IsNullOrEmpty(name)) return null;

            // 1) importer remap (after Extract Textures)
            var importer = AssetImporter.GetAtPath(assetPath);
            foreach (var kv in importer.GetExternalObjectMap())
                if (kv.Key.type == typeof(Texture) && kv.Key.name == name && kv.Value is Texture mapped) return mapped;
            // 2) a texture with that name next to the FBX (including subfolders)
            var dir = Path.GetDirectoryName(assetPath);
            foreach (var guid in AssetDatabase.FindAssets($"{name} t:Texture", new[] { dir }))
            {
                var p = AssetDatabase.GUIDToAssetPath(guid);
                if (Path.GetFileNameWithoutExtension(p) == name) return AssetDatabase.LoadAssetAtPath<Texture>(p);
            }
            // 3) embedded sub-asset
            return AssetDatabase.LoadAllAssetsAtPath(assetPath).OfType<Texture>().FirstOrDefault(x => x.name == name);
        }

        static void MarkAsNormalMap(Texture tex)
        {
            if (AssetImporter.GetAtPath(AssetDatabase.GetAssetPath(tex)) is TextureImporter ti && ti.textureType != TextureImporterType.NormalMap)
            {
                ti.textureType = TextureImporterType.NormalMap;
                ti.SaveAndReimport();
            }
        }

        // --- write to the first existing slot -----------------------------------------
        static void SetTexture(Material m, Texture t, params string[] names) { foreach (var n in names) if (m.HasProperty(n)) { m.SetTexture(n, t); return; } }
        static void SetColor(Material m, Color c, params string[] names) { foreach (var n in names) if (m.HasProperty(n)) { m.SetColor(n, c); return; } }
        static void SetFloat(Material m, float v, params string[] names) { foreach (var n in names) if (m.HasProperty(n)) { m.SetFloat(n, v); return; } }
    }
}
