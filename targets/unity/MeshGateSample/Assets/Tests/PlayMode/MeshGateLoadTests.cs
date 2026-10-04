// MeshGate — PlayMode tests: the canonical GLB loads into Unity according to the contract.
//   Unity -batchmode -nographics -projectPath targets/unity/MeshGateSample -runTests -testPlatform PlayMode -testResults TestResults/playmode.xml
using System.Collections;
using System.IO;
using System.Linq;
using MeshGate;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

public class MeshGateLoadTests
{
    static string DemoGlb()
    {
        // StreamingAssets first (after "Build Demo Scene"), otherwise straight from the repository's samples/.
        var sa = Path.Combine(Application.streamingAssetsPath, "meshgate_demo.glb");
        if (File.Exists(sa)) return sa;
        var repo = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", "meshgate_demo.glb"));
        Assert.IsTrue(File.Exists(repo), "samples/meshgate_demo.glb missing — export it from Blender");
        return repo;
    }

    [UnityTest]
    public IEnumerator DemoAssetLoadsByContract()
    {
        var go = new GameObject("asset");
        var asset = go.AddComponent<MeshGateAsset>();
        asset.loadOnStart = false;
        asset.colliders = MeshGateColliders.Mesh;
        var task = asset.LoadAsync(DemoGlb());
        while (!task.IsCompleted) yield return null;
        Assert.IsTrue(task.Result, "LoadAsync returned false");
        Assert.IsTrue(asset.IsLoaded);

        // glTF names and hierarchy are preserved.
        foreach (var name in new[] { "meshgate_demo", "crate_body", "crate_lid", "beacon_post", "beacon_ring", "beacon_notch", "handle_l", "handle_r" })
            Assert.IsNotNull(asset.Find(name), "missing node " + name);
        Assert.AreEqual("beacon_post", asset.Find("beacon_ring").parent.name, "beacon_ring must be a child of beacon_post");
        Assert.AreEqual("crate_lid", asset.Find("beacon_post").parent.name, "beacon_post must be a child of crate_lid");
        Assert.AreEqual("crate_body", asset.Find("crate_lid").parent.name);

        // Contract: applied transforms — scale 1 on every node.
        foreach (var t in asset.Root.GetComponentsInChildren<Transform>(true))
            Assert.That(Vector3.Distance(t.localScale, Vector3.one), Is.LessThan(1e-3f), $"scale ≠ 1 on {t.name}");

        // Meters and Y-up: bounds 0.83 × 0.71 × 0.52 (same as the validator and web viewer), bottom at y = 0.
        var s = asset.Bounds.size;
        Assert.AreEqual(0.832f, s.x, 0.02f, "width");
        Assert.AreEqual(0.707f, s.y, 0.02f, "height (Y-up)");
        Assert.AreEqual(0.524f, s.z, 0.02f, "depth");
        Assert.AreEqual(0f, asset.Bounds.min.y, 0.02f, "origin at the base");

        // Geometry and materials.
        Assert.AreEqual(17, asset.MeshCount);
        Assert.AreEqual(5244, asset.TriangleCount, 12);
        Assert.AreEqual(4, asset.MaterialCount);
        Assert.IsTrue(asset.Root.GetComponentsInChildren<MeshCollider>(true).Length >= 17, "colliders");

        // Animations by name.
        CollectionAssert.AreEquivalent(new[] { "lid_open", "beacon_spin" }, asset.AnimationNames);
        Assert.IsTrue(asset.IsPlaying, "autoplay");
        asset.Solo("lid_open");
        Assert.IsTrue(asset.LegacyAnimation.IsPlaying("lid_open"));
        Assert.IsFalse(asset.LegacyAnimation.IsPlaying("beacon_spin"));

        // The lid actually opens: after 1.5 s the rotation differs noticeably from the initial one.
        var lid = asset.Find("crate_lid");
        var startRot = lid.localRotation;
        asset.LegacyAnimation["lid_open"].time = 1.5f;
        asset.LegacyAnimation.Sample();
        Assert.That(Quaternion.Angle(startRot, lid.localRotation), Is.GreaterThan(60f), "lid did not open");

        Object.Destroy(go);
    }

    [UnityTest]
    public IEnumerator MissingFileReportsFailure()
    {
        var go = new GameObject("asset");
        var asset = go.AddComponent<MeshGateAsset>();
        asset.loadOnStart = false;
        var failed = false;
        asset.onFailed.AddListener(_ => failed = true);
        LogAssert.ignoreFailingMessages = true;
        var task = asset.LoadAsync(Path.Combine(Application.temporaryCachePath, "nope.glb"));
        while (!task.IsCompleted) yield return null;
        LogAssert.ignoreFailingMessages = false;
        Assert.IsFalse(task.Result);
        Assert.IsTrue(failed);
        Assert.IsFalse(asset.IsLoaded);
        Object.Destroy(go);
    }
}
