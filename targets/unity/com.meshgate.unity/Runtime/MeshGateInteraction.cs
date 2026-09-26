// MeshGate — hover/click on asset nodes (counterpart of the web viewer's hover/click).
// Requires colliders: if MeshGateAsset has them disabled, enables Mesh colliders.
using UnityEngine;
using UnityEngine.Events;

namespace MeshGate
{
    [AddComponentMenu("MeshGate/MeshGate Interaction")]
    [RequireComponent(typeof(MeshGateAsset))]
    public class MeshGateInteraction : MonoBehaviour
    {
        public Camera targetCamera;
        public bool highlight = true;
        public Color highlightTint = new Color(0.75f, 0.6f, 1f, 1f);
        public LayerMask mask = ~0;

        public UnityEvent<Transform> onHoverEnter = new UnityEvent<Transform>();
        public UnityEvent<Transform> onHoverExit = new UnityEvent<Transform>();
        public UnityEvent<Transform> onClick = new UnityEvent<Transform>();

        public Transform Hovered { get; private set; }
        public Transform Selected { get; private set; }

        MeshGateAsset _asset;
        static readonly int[] TintIds = { Shader.PropertyToID("baseColorFactor"), Shader.PropertyToID("_BaseColor"), Shader.PropertyToID("_Color") };
        MaterialPropertyBlock _mpb;
        Vector3 _downPos;

        void Awake()
        {
            _asset = GetComponent<MeshGateAsset>();
            _mpb = new MaterialPropertyBlock();   // cannot be created in a field initializer
            if (_asset.colliders == MeshGateColliders.None) _asset.colliders = MeshGateColliders.Mesh;
        }

        void Update()
        {
            var cam = targetCamera ? targetCamera : Camera.main;
            if (!cam || !_asset.IsLoaded || !MeshGateInput.Available) return;
            var mouse = (Vector3)MeshGateInput.MousePosition;
            var hit = Raycast(cam, mouse);
            SetHovered(hit);
            if (MeshGateInput.MouseButtonDown(0)) _downPos = mouse;
            if (MeshGateInput.MouseButtonUp(0) && (mouse - _downPos).sqrMagnitude < 36f)
            {
                Selected = hit;
                if (hit) onClick.Invoke(hit);
            }
        }

        Transform Raycast(Camera cam, Vector3 screenPos)
        {
            var ray = cam.ScreenPointToRay(screenPos);
            if (!Physics.Raycast(ray, out var hit, 1000f, mask)) return null;
            return hit.transform.IsChildOf(_asset.Root) ? hit.transform : null;
        }

        void SetHovered(Transform t)
        {
            if (t == Hovered) return;
            if (Hovered) { Tint(Hovered, false); onHoverExit.Invoke(Hovered); }
            Hovered = t;
            if (Hovered) { Tint(Hovered, true); onHoverEnter.Invoke(Hovered); }
        }

        void Tint(Transform t, bool on)
        {
            if (!highlight) return;
            foreach (var r in t.GetComponentsInChildren<Renderer>())
            {
                if (!on) { r.SetPropertyBlock(null); continue; }
                r.GetPropertyBlock(_mpb);
                foreach (var id in TintIds) _mpb.SetColor(id, highlightTint);
                r.SetPropertyBlock(_mpb);
            }
        }
    }
}
