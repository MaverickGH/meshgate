// MeshGate — simple IMGUI HUD for the demo scene: asset summary, names under the cursor, clip switching.
using System.Linq;
using UnityEngine;

namespace MeshGate
{
[AddComponentMenu("MeshGate/MeshGate HUD")]
public class MeshGateHud : MonoBehaviour
{
    MeshGateAsset _asset;
    MeshGateInteraction _interaction;
    string _hover = "";
    string _clicked = "";

    void Start()
    {
        _asset = FindFirstObjectByType<MeshGateAsset>();
        _interaction = FindFirstObjectByType<MeshGateInteraction>();
        if (_interaction)
        {
            _interaction.onHoverEnter.AddListener(t => _hover = t.name);
            _interaction.onHoverExit.AddListener(_ => _hover = "");
            _interaction.onClick.AddListener(t => _clicked = t.name);
        }
    }

    void OnGUI()
    {
        GUILayout.BeginArea(new Rect(12, 12, 360, 400), GUI.skin.box);
        GUILayout.Label("<b>MeshGate</b> · Unity (glTFast)", new GUIStyle(GUI.skin.label) { richText = true, fontSize = 15 });
        if (_asset == null || !_asset.IsLoaded) { GUILayout.Label("loading…"); GUILayout.EndArea(); return; }
        var s = _asset.Bounds.size;
        GUILayout.Label($"{_asset.source} · {_asset.LoadMilliseconds:0} ms");
        GUILayout.Label($"bounds {s.x:0.00} × {s.y:0.00} × {s.z:0.00} m");
        GUILayout.Label($"{_asset.MeshCount} meshes · {_asset.TriangleCount:n0} tris · {_asset.MaterialCount} materials" + (_asset.BoneCount > 0 ? $" · {_asset.BoneCount} bones" : ""));
        GUILayout.Label($"nodes: {string.Join(", ", _asset.NodeNames.Take(8))}…");
        GUILayout.Space(6);
        GUILayout.Label("animations:");
        GUILayout.BeginHorizontal();
        foreach (var clip in _asset.AnimationNames) if (GUILayout.Button(clip)) _asset.Solo(clip);
        if (GUILayout.Button("all")) _asset.Play();
        if (GUILayout.Button(_asset.IsPlaying ? "⏸" : "▶")) { if (_asset.IsPlaying) _asset.Stop(); else _asset.Play(); }
        GUILayout.EndHorizontal();
        var speed = GUILayout.HorizontalSlider(_asset.speed, 0.1f, 3f);
        if (!Mathf.Approximately(speed, _asset.speed)) _asset.SetSpeed(speed);
        GUILayout.Space(6);
        GUILayout.Label($"hovered: {_hover}");
        GUILayout.Label($"clicked: {_clicked}");
        GUILayout.Label("LMB — orbit · RMB — pan · wheel — zoom · F — frame");
        GUILayout.EndArea();
    }
}
}
