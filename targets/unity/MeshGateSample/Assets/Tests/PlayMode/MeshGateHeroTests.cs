// MeshGate — character PlayMode test: skin, bones with Unity Humanoid names, clips, UVs.
using System.Collections;
using System.IO;
using System.Linq;
using MeshGate;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

public class MeshGateHeroTests
{
    static string HeroGlb()
    {
        var sa = Path.Combine(Application.streamingAssetsPath, "meshgate_hero.glb");
        if (File.Exists(sa)) return sa;
        var repo = Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", "meshgate_hero.glb"));
        Assert.IsTrue(File.Exists(repo), "samples/meshgate_hero.glb missing — generate it with make_demo_character.py");
        return repo;
    }

    [UnityTest]
    public IEnumerator HeroLoadsWithSkeletonAndClips()
    {
        var go = new GameObject("hero");
        var asset = go.AddComponent<MeshGateAsset>();
        asset.loadOnStart = false;
        asset.autoplay = false;   // measure bounds in the T-pose
        var task = asset.LoadAsync(HeroGlb());
        while (!task.IsCompleted) yield return null;
        Assert.IsTrue(task.Result);

        Assert.AreEqual(1, asset.SkinnedMeshCount, "one skinned mesh");
        Assert.AreEqual(21, asset.BoneCount, "21 bones");
        foreach (var b in new[] { "Hips", "Spine", "Chest", "Neck", "Head", "LeftUpperArm", "RightLowerArm", "LeftFoot", "RightToes" })
            Assert.IsNotNull(asset.Find(b), "missing bone " + b);
        Assert.AreEqual("Chest", asset.Find("RightShoulder").parent.name);
        var smr = asset.Root.GetComponentInChildren<SkinnedMeshRenderer>();
        Assert.IsTrue(smr.sharedMesh.uv.Length == smr.sharedMesh.vertexCount, "UVs on all vertices");
        Assert.IsTrue(smr.sharedMesh.boneWeights.Length == smr.sharedMesh.vertexCount, "weights on all vertices");

        var s = asset.Bounds.size;
        Assert.AreEqual(1.75f, s.y, 0.05f, "height 1.75 m (Y-up)");
        Assert.AreEqual(0f, asset.Bounds.min.y, 0.03f, "stands on the floor");
        CollectionAssert.AreEquivalent(new[] { "idle", "wave" }, asset.AnimationNames);

        // wave actually raises the right hand
        var hand = asset.Find("RightHand");
        var y0 = hand.position.y;
        asset.Solo("wave");
        asset.LegacyAnimation["wave"].time = 1.0f;
        asset.LegacyAnimation.Sample();
        Assert.That(hand.position.y - y0, Is.GreaterThan(0.15f), "hand did not rise");
        Object.Destroy(go);
    }
}
