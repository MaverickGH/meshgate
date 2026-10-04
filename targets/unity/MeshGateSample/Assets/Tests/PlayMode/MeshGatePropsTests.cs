// MeshGate — props: each GLB from samples/ loads, with its nodes and clips in place.
using System.Collections;
using System.IO;
using MeshGate;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

public class MeshGatePropsTests
{
    static string Sample(string name)
    {
        var sa = Path.Combine(Application.streamingAssetsPath, name);
        if (File.Exists(sa)) return sa;
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "..", "samples", name));
    }

    static IEnumerator Load(string name, System.Action<MeshGateAsset> check)
    {
        var path = Sample(name);
        if (!File.Exists(path)) Assert.Ignore("missing " + name);
        var go = new GameObject(name);
        var asset = go.AddComponent<MeshGateAsset>();
        asset.loadOnStart = false; asset.autoplay = false;
        var task = asset.LoadAsync(path);
        while (!task.IsCompleted) yield return null;
        Assert.IsTrue(task.Result, name + " failed to load");
        check(asset);
        Object.Destroy(go);
    }

    [UnityTest] public IEnumerator Lantern() => Load("meshgate_lantern.glb", a =>
    {
        Assert.IsNotNull(a.Find("hang_pivot")); Assert.IsNotNull(a.Find("flame")); Assert.IsNotNull(a.Find("glass_body"));
        CollectionAssert.AreEquivalent(new[] { "swing", "flicker" }, a.AnimationNames);
        Assert.AreEqual(0.50f, a.Bounds.size.y, 0.03f, "lantern height");
    });

    [UnityTest] public IEnumerator Barrel() => Load("meshgate_barrel.glb", a =>
    {
        Assert.IsNotNull(a.Find("barrel_body")); Assert.IsNotNull(a.Find("hoop_3"));
        Assert.AreEqual(0, a.AnimationNames.Count);
        Assert.AreEqual(0.92f, a.Bounds.size.y, 0.03f, "barrel height");
        Assert.AreEqual(0f, a.Bounds.min.y, 0.02f, "stands on the floor");
        var mr = a.Find("barrel_body").GetComponent<MeshRenderer>();
        Assert.IsTrue(mr.sharedMaterial.HasProperty("_BumpMap") ? mr.sharedMaterial.GetTexture("_BumpMap") != null : mr.sharedMaterial.GetTexture("normalTexture") != null, "normal map not assigned");
    });

    [UnityTest] public IEnumerator Drone() => Load("meshgate_drone.glb", a =>
    {
        Assert.IsNotNull(a.Find("hover_pivot")); Assert.IsNotNull(a.Find("rotor_3")); Assert.IsNotNull(a.Find("blade_3_1"));
        Assert.AreEqual("motor_3", a.Find("rotor_3").parent.name);
        CollectionAssert.AreEquivalent(new[] { "hover", "rotors" }, a.AnimationNames);
        Assert.AreEqual(24, a.MeshCount);
    });
}
