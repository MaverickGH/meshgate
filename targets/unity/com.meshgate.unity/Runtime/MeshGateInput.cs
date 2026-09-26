// MeshGate — input for interaction and orbit: legacy Input Manager or the new Input System, whichever is enabled.
using UnityEngine;
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace MeshGate
{
    public static class MeshGateInput
    {
        public static bool Available =>
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            Mouse.current != null;
#elif ENABLE_LEGACY_INPUT_MANAGER
            true;
#else
            false;
#endif

        public static Vector2 MousePosition
        {
            get
            {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
                return Mouse.current != null ? Mouse.current.position.ReadValue() : Vector2.zero;
#elif ENABLE_LEGACY_INPUT_MANAGER
                return Input.mousePosition;
#else
                return Vector2.zero;
#endif
            }
        }

        public static bool MouseButton(int button)
        {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var m = Mouse.current; if (m == null) return false;
            return button == 0 ? m.leftButton.isPressed : button == 1 ? m.rightButton.isPressed : m.middleButton.isPressed;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButton(button);
#else
            return false;
#endif
        }

        public static bool MouseButtonDown(int button)
        {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var m = Mouse.current; if (m == null) return false;
            return button == 0 ? m.leftButton.wasPressedThisFrame : button == 1 ? m.rightButton.wasPressedThisFrame : m.middleButton.wasPressedThisFrame;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButtonDown(button);
#else
            return false;
#endif
        }

        public static bool MouseButtonUp(int button)
        {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var m = Mouse.current; if (m == null) return false;
            return button == 0 ? m.leftButton.wasReleasedThisFrame : button == 1 ? m.rightButton.wasReleasedThisFrame : m.middleButton.wasReleasedThisFrame;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetMouseButtonUp(button);
#else
            return false;
#endif
        }

        /// <summary>Scroll in wheel "ticks" (the new Input System reports pixels, so we normalize).</summary>
        public static float Scroll
        {
            get
            {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
                return Mouse.current != null ? Mouse.current.scroll.ReadValue().y / 120f : 0f;
#elif ENABLE_LEGACY_INPUT_MANAGER
                return Input.mouseScrollDelta.y;
#else
                return 0f;
#endif
            }
        }

        public static bool KeyDown(KeyCode key)
        {
#if MESHGATE_INPUT_SYSTEM && ENABLE_INPUT_SYSTEM
            var k = Keyboard.current; if (k == null) return false;
            switch (key)
            {
                case KeyCode.F: return k.fKey.wasPressedThisFrame;
                case KeyCode.Space: return k.spaceKey.wasPressedThisFrame;
                case KeyCode.R: return k.rKey.wasPressedThisFrame;
                default: return false;
            }
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(key);
#else
            return false;
#endif
        }
    }
}
