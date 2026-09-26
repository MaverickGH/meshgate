[English](THIRD_PARTY_NOTICES.md) · **Русский**

# Сторонние компоненты

MeshGate — проприетарное ПО (см. [LICENSE](LICENSE)). Он включает или скачивает компоненты ниже, которые сохраняют свои
лицензии.

| Компонент | Где | Лицензия |
|---|---|---|
| [three.js](https://github.com/mrdoob/three.js) 0.169.0 | Вьюер студии и `targets/web` (в комплекте или с CDN) | MIT |
| [IBM Plex Sans](https://github.com/IBM/plex) | Шрифт интерфейса студии, `apps/studio/ui/fonts` | SIL Open Font License 1.1 (`apps/studio/ui/fonts/LICENSE.txt`) |
| [Tauri](https://tauri.app) 2 | Оболочка приложения MeshGate Studio | MIT или Apache-2.0 |
| [TripoSR](https://github.com/VAST-AI-Research/TripoSR) | Скачивается по запросу `meshgate.py gen --setup triposr` в `~/.cache/meshgate` | MIT (код и веса) |
| [glTFast](https://github.com/Unity-Technologies/com.unity.cloud.gltfast) | Зависимость для Unity, ставится через Package Manager | Apache-2.0 |
| [glTFRuntime](https://github.com/rdeioris/glTFRuntime) | Необязательный плагин Unreal, ставишь сам | MIT |

Blender, Unity, Godot и Unreal Engine — отдельные продукты со своими лицензиями, MeshGate их не включает. ИИ-инструменты
(Claude Code, Codex, Gemini, Ollama) и облачные сервисы (Meshy, Tripo, fal, OpenAI) работают под твоими аккаунтами и по
их условиям.
