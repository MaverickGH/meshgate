// MeshGate — orbit camera that auto-frames the asset bounds
// (same behavior as the web viewer: LMB — orbit, RMB — pan, wheel — zoom, F — frame).
using UnityEngine;

namespace MeshGate
{
    [AddComponentMenu("MeshGate/MeshGate Orbit Camera")]
    [RequireComponent(typeof(Camera))]
    public class MeshGateOrbitCamera : MonoBehaviour
    {
        [Tooltip("Asset to frame after it loads (optional)")]
        public MeshGateAsset target;
        public Vector3 pivot;
        public float distance = 3f;
        public float yaw = 35f, pitch = 20f;
        public float rotateSpeed = 0.25f, zoomSpeed = 0.12f, panSpeed = 0.002f;
        public float minPitch = -85f, maxPitch = 85f;

        Camera _cam;
        Vector3 _last;

        void Awake()
        {
            _cam = GetComponent<Camera>();
            if (target) target.onLoaded.AddListener(a => Frame(a.Bounds));
        }

        public void Frame(Bounds b)
        {
            pivot = b.center;
            var radius = Mathf.Max(b.extents.magnitude, 0.05f);
            distance = radius / Mathf.Sin(_cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.15f;
            _cam.nearClipPlane = Mathf.Max(radius / 200f, 0.001f);
            _cam.farClipPlane = Mathf.Max(radius * 200f, 50f);
            Apply();
        }

        void LateUpdate()
        {
            if (MeshGateInput.Available)
            {
                var pos = (Vector3)MeshGateInput.MousePosition;
                var delta = pos - _last; _last = pos;
                if (MeshGateInput.MouseButton(0)) { yaw += delta.x * rotateSpeed; pitch = Mathf.Clamp(pitch - delta.y * rotateSpeed, minPitch, maxPitch); }
                if (MeshGateInput.MouseButton(1)) pivot -= (transform.right * delta.x + transform.up * delta.y) * (panSpeed * distance);
                var scroll = MeshGateInput.Scroll;
                if (Mathf.Abs(scroll) > 0f) distance = Mathf.Max(0.01f, distance * (1f - scroll * zoomSpeed));
                if (MeshGateInput.KeyDown(KeyCode.F) && target && target.IsLoaded) Frame(target.Bounds);
            }
            Apply();
        }

        void Apply()
        {
            var rot = Quaternion.Euler(pitch, yaw, 0f);
            transform.rotation = rot;
            transform.position = pivot - rot * Vector3.forward * distance;
        }
    }
}
