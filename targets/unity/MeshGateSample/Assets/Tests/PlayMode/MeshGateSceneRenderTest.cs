// MeshGate — renders the demo scene to PNG (visual check without opening the editor).
// Run without -nographics:
//   Unity -batchmode -projectPath targets/unity/MeshGateSample -runTests -testPlatform PlayMode -testFilter MeshGateSceneRenderTest
// Output: TestResults/meshgate_unity.png (or the path from the MESHGATE_SHOT environment variable).
using System.Collections;
using System.IO;
using System.Linq;
using MeshGate;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

public class MeshGateSceneRenderTest
{
    [UnityTest]
    public IEnumerator DemoSceneRendersToPng()
    {
        if (SystemInfo.graphicsDeviceType == UnityEngine.Rendering.GraphicsDeviceType.Null)
            Assert.Ignore("running with -nographics — rendering unavailable");

        yield return SceneManager.LoadSceneAsync("Assets/MeshGate/MeshGateDemo.unity", LoadSceneMode.Single);
        var asset = Object.FindObjectsByType<MeshGateAsset>(FindObjectsSortMode.None).FirstOrDefault(a => a.source == "meshgate_demo.glb");
        Assert.IsNotNull(asset, "no MeshGateAsset with the crate in the scene — build it via MeshGate → Sample → Build Demo Scene");
        var t = 0f;
        while (!asset.IsLoaded && t < 20f) { t += Time.deltaTime; yield return null; }
        Assert.IsTrue(asset.IsLoaded, "asset did not load within 20 s");

        // Put the lid in the open position so the shot shows the animation and hierarchy.
        asset.LegacyAnimation["lid_open"].time = 1.5f;
        asset.LegacyAnimation.Sample();
        asset.Stop();
        yield return null;

        var cam = Camera.main;
        var orbit = cam.GetComponent<MeshGateOrbitCamera>();
        // Frame all three assets: FBX on the left, glTF import in the center, runtime on the right.
        var b = asset.Bounds;
        b.Encapsulate(new Vector3(-1.2f - 0.45f, 0f, 0f));
        b.Encapsulate(new Vector3(-0.7f, 1.8f, 1.2f)); b.Encapsulate(new Vector3(0.7f, 1.8f, 1.2f));
        foreach (var a in Object.FindObjectsByType<MeshGateAsset>(FindObjectsSortMode.None))
        {
            var wait = 0f; while (!a.IsLoaded && wait < 20f) { wait += Time.deltaTime; yield return null; }
            if (System.Linq.Enumerable.Contains(a.AnimationNames, "wave")) { a.Solo("wave"); a.LegacyAnimation["wave"].time = 1.0f; a.LegacyAnimation.Sample(); a.Stop(); }
        }
        orbit.yaw = 25f; orbit.pitch = 18f;
        orbit.Frame(b);
        yield return null;

        const int w = 1280, h = 800;
        var rt = new RenderTexture(w, h, 24);
        cam.targetTexture = rt;
        cam.Render();
        RenderTexture.active = rt;
        var tex = new Texture2D(w, h, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
        tex.Apply();
        cam.targetTexture = null;
        RenderTexture.active = null;

        var path = System.Environment.GetEnvironmentVariable("MESHGATE_SHOT");
        if (string.IsNullOrEmpty(path)) path = Path.Combine(Application.dataPath, "..", "TestResults", "meshgate_unity.png");
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        File.WriteAllBytes(path, tex.EncodeToPNG());
        Debug.Log("MeshGate: scene shot → " + Path.GetFullPath(path));

        // Non-empty frame: some pixels differ noticeably from the background.
        var bg = tex.GetPixel(2, 2);
        var different = 0;
        for (var y = 0; y < h; y += 8) for (var x = 0; x < w; x += 8)
            if (((Vector4)(tex.GetPixel(x, y) - bg)).sqrMagnitude > 0.01f) different++;
        Assert.That(different, Is.GreaterThan(200), "frame is almost empty — asset did not render");
        Object.Destroy(rt); Object.Destroy(tex);
    }
}
