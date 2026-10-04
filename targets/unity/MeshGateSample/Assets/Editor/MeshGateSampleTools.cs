// MeshGate — headless check of the sample project (all logic lives in the package: MeshGate.Editor.MeshGateDemoScene).
//   Unity -batchmode -nographics -projectPath targets/unity/MeshGateSample -executeMethod MeshGateSampleTools.BuildAll -quit
using System.IO;
using MeshGate.Editor;
using UnityEditor;
using UnityEngine;

public static class MeshGateSampleTools
{
    static string Samples => Path.Combine(MeshGateMenu.FindRepoRoot() ?? "", "samples");

    [MenuItem("MeshGate/Sample/Build Demo Scene")]
    public static void BuildDemoScene()
    {
        MeshGateDemoScene.Build(Samples);
        var scenes = new System.Collections.Generic.List<EditorBuildSettingsScene> { new EditorBuildSettingsScene(MeshGateDemoScene.ScenePath, true) };
        if (MeshGateDemoScene.CopyPack(Samples))
        {
            MeshGateDemoScene.BuildPackScene();
            foreach (var tier in MeshGateDemoScene.PackSceneTiers)
                scenes.Add(new EditorBuildSettingsScene(MeshGateDemoScene.PackScenePathFor(tier), true));
        }
        if (MeshGateDemoScene.CopyGeneratedPack(Samples))
        {
            MeshGateDemoScene.BuildTierShowcaseScene();
            scenes.Add(new EditorBuildSettingsScene(MeshGateDemoScene.TierShowcasePath, true));
        }
        EditorBuildSettings.scenes = scenes.ToArray();
    }

    /// <summary>Full check: copy GLB/FBX, editor import, scene, contract validator, FBX↔GLB comparison.</summary>
    public static void BuildAll()
    {
        BuildDemoScene();
        Debug.Log(MeshGateDemoScene.Verify());
        Debug.Log(MeshGateMenu.Validate(Path.Combine(Samples, MeshGateDemoScene.GlbName), strict: true));
        Debug.Log(MeshGateDemoScene.VerifyPack());
        Debug.Log("MeshGate: BuildAll OK");
    }
}
