// MeshGate — example packs: every asset of samples/packs/zombie_cats loads at runtime with the clips, bones and size
// written in the pack's index.json, the pack scene renders, and the generated pack loads on every quality tier.
using System;
using System.Collections;
using System.IO;
using System.Linq;
using MeshGate;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

public class MeshGatePackTests
{
    [Serializable] class PackAsset { public string file; public string kind; public string[] clips; public int bones; public float[] dims_m; }
    [Serializable] class PackIndex { public PackAsset[] assets; }

    static string PackDir()
    {
        var sa = Path.Combine(Application.streamingAssetsPath, "packs", "zombie_cats");
        if (Directory.Exists(sa)) return sa;
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", "packs", "zombie_cats"));
    }

    [UnityTest]
    public IEnumerator EveryPackAssetLoadsAsIndexed()
    {
        var dir = PackDir();
        if (!File.Exists(Path.Combine(dir, "index.json"))) Assert.Ignore("pack not generated");
        var index = JsonUtility.FromJson<PackIndex>(File.ReadAllText(Path.Combine(dir, "index.json")));
        Assert.That(index.assets.Length, Is.GreaterThanOrEqualTo(12));
        foreach (var a in index.assets)
        {
            var go = new GameObject(a.file);
            var asset = go.AddComponent<MeshGateAsset>();
            asset.loadOnStart = false; asset.autoplay = false;
            var task = asset.LoadAsync(Path.Combine(dir, a.file));
            while (!task.IsCompleted) yield return null;
            Assert.IsTrue(task.Result, a.file + " did not load");
            CollectionAssert.AreEquivalent(a.clips ?? new string[0], asset.AnimationNames.ToArray(), a.file + ": clips");
            Assert.AreEqual(a.bones, asset.BoneCount, a.file + ": bones");
            Assert.AreEqual(a.dims_m[1], asset.Bounds.size.y, 0.05f, a.file + ": height (Y-up, meters)");
            Assert.AreEqual(0f, asset.Bounds.min.y, 0.05f, a.file + ": stands on the ground");
            UnityEngine.Object.Destroy(go);
            yield return null;
        }
    }

    static string GeneratedDir()
    {
        var sa = Path.Combine(Application.streamingAssetsPath, "packs", "generated");
        if (Directory.Exists(sa)) return sa;
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", "packs", "generated"));
    }

    // Assets made by `meshgate.py gen` (kit code from text and from a picture, a TripoSR mesh): the canonical file loads
    // as indexed, and every quality-tier file loads within that tier's triangle budget.
    [UnityTest]
    public IEnumerator GeneratedPackLoadsEveryTier()
    {
        var dir = GeneratedDir();
        if (!File.Exists(Path.Combine(dir, "index.json"))) Assert.Ignore("generated pack not built (sources/generate/make_generated_pack.py)");
        var index = JsonUtility.FromJson<PackIndex>(File.ReadAllText(Path.Combine(dir, "index.json")));
        Assert.That(index.assets.Length, Is.GreaterThanOrEqualTo(6));
        var budgets = new[] { ("mobile-low", 8000), ("mobile-mid", 25000), ("mobile-high", 60000) };
        int tierFiles = 0;
        foreach (var a in index.assets)
        {
            var go = new GameObject(a.file);
            var asset = go.AddComponent<MeshGateAsset>();
            asset.loadOnStart = false; asset.autoplay = false; asset.useQualityVariant = false;
            var task = asset.LoadAsync(Path.Combine(dir, a.file));
            while (!task.IsCompleted) yield return null;
            Assert.IsTrue(task.Result, a.file + " did not load");
            CollectionAssert.AreEquivalent(a.clips ?? new string[0], asset.AnimationNames.ToArray(), a.file + ": clips");
            Assert.AreEqual(a.dims_m[1], asset.Bounds.size.y, 0.05f, a.file + ": height (Y-up, meters)");
            Assert.AreEqual(0f, asset.Bounds.min.y, 0.05f, a.file + ": stands on the ground");
            UnityEngine.Object.Destroy(go);
            foreach (var (tier, budget) in budgets)
            {
                var file = Path.GetFileNameWithoutExtension(a.file) + "." + tier + ".glb";
                if (!File.Exists(Path.Combine(dir, file))) continue;
                var tgo = new GameObject(file);
                var t = tgo.AddComponent<MeshGateAsset>();
                t.loadOnStart = false; t.autoplay = false; t.useQualityVariant = false;
                var tt = t.LoadAsync(Path.Combine(dir, file));
                while (!tt.IsCompleted) yield return null;
                Assert.IsTrue(tt.Result, file + " did not load");
                Assert.That(t.TriangleCount, Is.LessThanOrEqualTo(budget), file + ": over the " + tier + " budget");
                tierFiles++;
                UnityEngine.Object.Destroy(tgo);
            }
            yield return null;
        }
        Assert.That(tierFiles, Is.GreaterThanOrEqualTo(index.assets.Length * 3), "every asset has three tier files");
    }

    // GeneratedTiers.unity: every generated asset at every tier loads, triangles grow from mobile-low to pc and stay in each
    // tier's budget; with graphics the whole grid is saved as meshgate_unity_generated_tiers.png.
    [UnityTest]
    public IEnumerator GeneratedTierShowcase()
    {
        if (!File.Exists(Path.Combine(Application.dataPath, "MeshGate", "GeneratedTiers.unity"))) Assert.Ignore("GeneratedTiers scene not built");
        yield return SceneManager.LoadSceneAsync("Assets/MeshGate/GeneratedTiers.unity", LoadSceneMode.Single);
        var showcase = UnityEngine.Object.FindFirstObjectByType<MeshGateTierShowcase>();
        Assert.IsNotNull(showcase, "no MeshGateTierShowcase in the scene");
        var t0 = Time.realtimeSinceStartup;
        while (!showcase.Ready && Time.realtimeSinceStartup - t0 < 120f) yield return null;
        Assert.IsTrue(showcase.Ready, "showcase did not finish loading");
        Assert.AreEqual(0, showcase.Failed, "some copies failed to load");
        Assert.That(showcase.Rows, Is.GreaterThanOrEqualTo(6));
        foreach (var kv in showcase.Triangles)
        {
            var t = kv.Value;
            for (int c = 0; c < t.Length; c++)
            {
                Assert.That(t[c], Is.GreaterThan(0), $"{kv.Key} {MeshGateTierShowcase.Tiers[c]}: missing");
                Assert.That(t[c], Is.LessThanOrEqualTo(MeshGateTierShowcase.Budgets[c]), $"{kv.Key} {MeshGateTierShowcase.Tiers[c]}: over budget");
                if (c > 0) Assert.That(t[c], Is.GreaterThanOrEqualTo(t[c - 1]), $"{kv.Key}: fewer tris on {MeshGateTierShowcase.Tiers[c]} than on {MeshGateTierShowcase.Tiers[c - 1]}");
            }
            Debug.Log($"MeshGate tiers: {kv.Key} " + string.Join(" / ", t.Select(v => v.ToString("N0"))));
        }
        if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) yield break;
        for (var i = 0; i < 30; i++) yield return null;
        var cam = Camera.main;
        const int w = 1800, h = 1400;
        var rt = new RenderTexture(w, h, 24) { antiAliasing = 4 };
        cam.targetTexture = rt;
        showcase.FrameCamera(cam);   // frame for the snapshot's aspect
        cam.Render(); RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply();
        cam.targetTexture = null; RenderTexture.active = null;
        var dir = Environment.GetEnvironmentVariable("MESHGATE_SHOT_DIR");
        if (string.IsNullOrEmpty(dir)) dir = Path.Combine(Application.dataPath, "..", "TestResults");
        Directory.CreateDirectory(dir);
        File.WriteAllBytes(Path.Combine(dir, "meshgate_unity_generated_tiers.png"), tex.EncodeToPNG());
        UnityEngine.Object.Destroy(rt); UnityEngine.Object.Destroy(tex);
    }

    [UnityTest]
    public IEnumerator ZombieCatShamblesAtRuntime()
    {
        var path = Path.Combine(PackDir(), "zc_zombie_cat.glb");
        if (!File.Exists(path)) Assert.Ignore("pack not generated");
        var go = new GameObject("cat");
        var asset = go.AddComponent<MeshGateAsset>();
        asset.loadOnStart = false; asset.playOnLoad = "shamble";
        var task = asset.LoadAsync(path);
        while (!task.IsCompleted) yield return null;
        Assert.IsTrue(asset.LegacyAnimation.IsPlaying("shamble"), "playOnLoad did not start shamble");
        Assert.IsFalse(asset.LegacyAnimation.IsPlaying("idle"));
        // T-pose: the hand is level with the shoulder along the arm; shambling, it reaches forward (along ±Z)
        asset.LegacyAnimation["shamble"].time = 0.5f; asset.LegacyAnimation.Sample();
        var hand = asset.Find("RightHand"); var shoulder = asset.Find("RightUpperArm");
        Assert.That(Mathf.Abs(hand.position.z - shoulder.position.z), Is.GreaterThan(0.12f), "arms did not reach forward");
        UnityEngine.Object.Destroy(go);
    }

    [UnityTest]
    public IEnumerator QualityTierPicksVariantAndSettings()
    {
        var dir = PackDir();
        if (!File.Exists(Path.Combine(dir, "zc_zombie_cat.mobile-low.glb"))) Assert.Ignore("tier variants not generated");
        try
        {
            MeshGateQuality.Apply(MeshGateTier.MobileLow);
            Assert.AreEqual(ShadowQuality.Disable, QualitySettings.shadows, "mobile-low: no shadows");
            Assert.AreEqual(SkinWeights.TwoBones, QualitySettings.skinWeights, "mobile-low: 2 bone influences");
            var go = new GameObject("cat-low");
            var asset = go.AddComponent<MeshGateAsset>();
            asset.loadOnStart = false; asset.autoplay = false;
            var task = asset.LoadAsync(Path.Combine(dir, "zc_zombie_cat.glb"));
            while (!task.IsCompleted) yield return null;
            Assert.AreEqual("zc_zombie_cat.mobile-low.glb", asset.LoadedFile, "variant not picked");
            Assert.That(asset.TriangleCount, Is.LessThanOrEqualTo(8000), "mobile-low tris budget");
            CollectionAssert.AreEquivalent(new[] { "idle", "shamble" }, asset.AnimationNames.ToArray());
            UnityEngine.Object.Destroy(go);

            MeshGateQuality.Apply(MeshGateTier.PC);
            var go2 = new GameObject("cat-pc");
            var pc = go2.AddComponent<MeshGateAsset>();
            pc.loadOnStart = false; pc.autoplay = false;
            var t2 = pc.LoadAsync(Path.Combine(dir, "zc_zombie_cat.glb"));
            while (!t2.IsCompleted) yield return null;
            Assert.AreEqual("zc_zombie_cat.glb", pc.LoadedFile);
            Assert.That(pc.TriangleCount, Is.GreaterThan(asset.TriangleCount * 5), "pc detail should be far higher than mobile-low");
            Assert.AreEqual(ShadowQuality.All, QualitySettings.shadows);
            UnityEngine.Object.Destroy(go2);
        }
        finally { MeshGateQuality.Restore(); }
    }

    [UnityTest]
    public IEnumerator ThreeQualityScenesRenderToPng()
    {
        if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null) Assert.Ignore("-nographics");
        foreach (var name in new[] { "Low", "Mid", "PC" })
        {
            var scenePath = $"Assets/MeshGate/ZombieCats_{name}.unity";
            if (!File.Exists(Path.Combine(Application.dataPath, "MeshGate", $"ZombieCats_{name}.unity"))) Assert.Ignore("pack scenes not built");
            yield return SceneManager.LoadSceneAsync(scenePath, LoadSceneMode.Single);
            for (var i = 0; i < 90; i++) yield return null;
            var cam = Camera.main;
            const int w = 1400, h = 800;
            var rt = new RenderTexture(w, h, 24);
            cam.targetTexture = rt; cam.Render(); RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0); tex.Apply();
            cam.targetTexture = null; RenderTexture.active = null;
            var dir = Environment.GetEnvironmentVariable("MESHGATE_SHOT_DIR");
            if (string.IsNullOrEmpty(dir)) dir = Path.Combine(Application.dataPath, "..", "TestResults");
            Directory.CreateDirectory(dir);
            File.WriteAllBytes(Path.Combine(dir, $"meshgate_unity_zombiecats_{name.ToLower()}.png"), tex.EncodeToPNG());
            Debug.Log($"MeshGate: {name} scene ({MeshGateQuality.CurrentId}) → snapshot, {UnityEngine.Object.FindObjectsByType<MeshFilter>(FindObjectsSortMode.None).Sum(m => m.sharedMesh ? m.sharedMesh.triangles.Length / 3 : 0):N0} static tris");
            UnityEngine.Object.Destroy(rt); UnityEngine.Object.Destroy(tex);
        }
        MeshGateQuality.Restore();
    }
}
