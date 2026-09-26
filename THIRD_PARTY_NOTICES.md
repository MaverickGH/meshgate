**English** · [Русский](THIRD_PARTY_NOTICES.ru.md)

# Third-party notices

MeshGate is proprietary (see [LICENSE](LICENSE)). It includes or downloads the components below, which keep their own
licenses.

| Component | Where | License |
|---|---|---|
| [three.js](https://github.com/mrdoob/three.js) 0.169.0 | Studio viewer and `targets/web` (bundled or from a CDN) | MIT |
| [IBM Plex Sans](https://github.com/IBM/plex) | Studio interface font, `apps/studio/ui/fonts` | SIL Open Font License 1.1 (`apps/studio/ui/fonts/LICENSE.txt`) |
| [Tauri](https://tauri.app) 2 | MeshGate Studio desktop shell | MIT or Apache-2.0 |
| [TripoSR](https://github.com/VAST-AI-Research/TripoSR) | Downloaded on request by `meshgate.py gen --setup triposr` into `~/.cache/meshgate` | MIT (code and weights) |
| [glTFast](https://github.com/Unity-Technologies/com.unity.cloud.gltfast) | Unity dependency, installed by Unity's Package Manager | Apache-2.0 |
| [glTFRuntime](https://github.com/rdeioris/glTFRuntime) | Optional Unreal plugin, installed by you | MIT |

Blender, Unity, Godot and Unreal Engine are separate products under their own licenses; MeshGate does not include
them. AI tools (Claude Code, Codex, Gemini, Ollama) and cloud services (Meshy, Tripo, fal, OpenAI) are used under
your own accounts and their terms.
