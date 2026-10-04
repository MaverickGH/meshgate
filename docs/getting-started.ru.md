[English](getting-started.md) · **Русский**

# С чего начать

MeshGate берёт 3D-ассет — сделанный в Blender, сгенерированный по описанию или картинке или скачанный — и доставляет
его в web, Unity, Godot и Unreal проверенными файлами, по одному на уровень качества. Эта страница проводит от свежего
клона до ассета в твоём движке. Все шаги установки для macOS, Windows и Linux и где MeshGate хранит файлы — в
[Установке](install.ru.md).

## 1. Что нужно

| Для чего | Что нужно | Заметки |
|---|---|---|
| Всё | **Python 3.9+** | Только стандартная библиотека; `pip install` не нужен |
| Экспорт, генерация, проверки | **Blender 3.5+** | Проверено на 3.5, 4.2 LTS и 5.2 LTS. Находится сам, или задай `MESHGATE_BLENDER` |
| Текст → 3D | Один **ИИ-инструмент командной строки** | Claude Code, Codex, Gemini или Ollama, с одним входом — см. шаг 4 |
| Картинка → 3D | **TripoSR** (локально) или облачный ключ | `meshgate.py gen --setup triposr` ставит TripoSR в `~/.cache/meshgate` (~3 ГБ, MIT) |
| Необязательно, потом | **Hunyuan3D-2** (картинка → 3D, ~10 ГБ) и **Kimodo** (текст → анимация персонажа, ~20 ГБ) | Ставятся отдельно: студия → **«Статус и ИИ»** → «Дополнительные компоненты», или `meshgate.py gen --setup hunyuan3d` / `kimodo`. Обоим нужна видеокарта NVIDIA; Kimodo ещё нужен доступ к Meta Llama 3 на Hugging Face |
| Web | Современный браузер | WebGL 2; Three.js приходит вместе с вьюером |
| Unity | **Unity 6000.0+** | glTFast 6.20 требует Unity 6 |
| Godot | **Godot 4.4+** | Проверено на 4.7.2 (Forward+) |
| Unreal | **UE 5.4–5.6** | Сверено с Python API; первый живой запуск ещё впереди |

## 2. Установка и проверка

```bash
git clone https://github.com/MaverickGH/meshgate.git
cd meshgate
python3 meshgate.py doctor
```

`doctor` показывает, что нашлось: Blender, аддон, движки, ИИ-инструменты с состоянием входа, генераторы сеток и
ключи. В конце он пишет, что сделать для недостающего.

## 3. Три способа работать

- **В Blender, без терминала.** `python3 meshgate.py install-blender` (сначала закрой Blender), затем **N → MeshGate**:
  отметь движки и уровни качества, нажми **Проверить**, **Исправить всё**, **Экспорт**. См.
  [sources/blender/README.ru.md](../sources/blender/README.ru.md).
- **MeshGate Studio.** Приложение для macOS и Windows или `python3 meshgate.py studio` в любом браузере: опиши модель
  или перетащи картинку, нажми **«Сгенерировать»**, смотри каждый уровень в 3D. См.
  [apps/studio/README.ru.md](../apps/studio/README.ru.md).
- **Командная строка.** `meshgate.py export`, `validate`, `gen` и `check` делают то же самое без интерфейса и в CI.

## 4. Подключить нейросеть

В студии нажми **«Статус и ИИ»**. Окно показывает Blender, Unity, Godot и Unreal с версиями и плагинами MeshGate и
состояние каждого ИИ-инструмента; ставит аддон Blender и ИИ-инструменты, запускает вход и сохраняет облачные ключи.
Через терминал:

| Инструмент | Установка | Войти один раз |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` | `claude auth login`, или задай `ANTHROPIC_API_KEY` |
| [Codex CLI](https://github.com/openai/codex) | `npm install -g @openai/codex` | `codex login`, или задай `OPENAI_API_KEY` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm install -g @google/gemini-cli` | запусти `gemini` и выбери вход, или задай `GEMINI_API_KEY` |
| [Ollama](https://ollama.com/download), без интернета | приложение с ollama.com | `ollama pull qwen2.5-coder:14b` |

Если Codex вошёл через ChatGPT, картинки по тексту тоже бесплатны: с `--concept sheet` gpt-image-2 сначала рисует лист
видов, и ИИ моделирует по нему. Облачным генераторам сеток нужен ключ: `MESHY_API_KEY`, `TRIPO_API_KEY` или `FAL_KEY`. `OPENAI_API_KEY` или `FAL_KEY`
ещё и рисуют картинку-образец, когда генератору по картинке дают текст. Ключи можно задать в окружении или сохранить в
студии. Студия пишет их в `~/.meshgate/keys.json`, файл читаешь только ты, и командная строка его тоже читает. Дальше:

```bash
python3 meshgate.py gen --list-ai                          # что готово
python3 meshgate.py gen "деревянный сундук с сокровищами" --size 0.8
python3 meshgate.py gen --image photo.jpg --size 0.8
```

Нужно намного меньше треугольников или совсем без текстур? `--tris 500` задаёт свой лимит (`low=150,pc=2000` по
уровням), а `--colors vertex` хранит цвета в вершинах. То же есть в студии. Подробнее — [docs/generation.ru.md](generation.ru.md).

## 5. Какие файлы пишет MeshGate

| Файл | Куда идёт |
|---|---|
| `<имя>.glb` | Канонический ассет (уровень PC): web, Unity, Godot, Interchange в Unreal |
| `<имя>.mobile-low.glb`, `.mobile-mid.glb`, `.mobile-high.glb` | Тот же ассет для каждого уровня телефонов, в пределах его бюджета |
| `<имя>.fbx` | Редакторы Unity и Unreal, персонажи Humanoid |
| `<имя>.unreal.fbx` | Статичные меши Unreal с коллизией `UCX_` |
| `<имя>.godot.glb` | Импорт в редактор Godot с коллизией `-convcolonly` |
| `<имя>.unity.fbx` | Unity с мешами `_LOD0…_LODn` для LOD Group |

Бюджеты уровней — в [docs/quality-tiers.ru.md](quality-tiers.ru.md); правила, которым следует каждый файл, — в
[docs/asset-contract.ru.md](asset-contract.ru.md).

## 6. Рекомендации по движкам

### Web (Three.js)

- **Используй библиотеку вьюера.** [`targets/web/meshgate-viewer.js`](../targets/web/meshgate-viewer.js) работает на
  Three.js r169 через import map. `createViewer(container, { quality: "auto" })` выбирает уровень по устройству. С
  `variants: true` он грузит `<имя>.<уровень>.glb` рядом с каноническим файлом, если такой есть. См.
  [targets/web/README.ru.md](../targets/web/README.ru.md).
- **Держи файлы уровней рядом.** `<имя>.glb` и его `.mobile-*.glb` лежат в одной папке. Отдавай их как
  `model/gltf-binary` с долгим кэшем: вьюер запрашивает их, только когда уровню они нужны.
- **Выбирай файлы под аудиторию.** Телефонам — `mobile-low` или `mobile-mid`. `.draco.glb` — только вместе с декодером
  Draco, вьюер берёт его с CDN Three.js. Для работы без интернета скопируй three.js локально командой
  `python3 scripts/vendor_three.py`.
- **Свечение выборочное.** На богатых уровнях светятся только излучающие материалы, яркие неосвещённые поверхности не
  засвечиваются.

### Unity

- **Поставь два пакета.** Сначала **glTFast** (`com.unity.cloud.gltfast`) из реестра Unity. Затем MeshGate: Package
  Manager → Add package from git URL:
  `https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity`.
- **Загрузка во время игры.** Добавь компонент **MeshGateAsset** и задай `source`. Относительные пути считаются от
  `StreamingAssets`. Он грузит канонический GLB и играет клипы по именам, а **MeshGateQuality** на сцене заставляет
  его брать `<имя>.<уровень>.glb` на мобильных уровнях.
- **Ассеты редактора.** Персонажи идут через `.fbx` с аватаром Humanoid: выдели файл и запусти **MeshGate → Set Up
  Humanoid (Selected FBX)**. Статичные предметы — любой из файлов; `.unity.fbx` несёт меши `_LOD`, готовые для LOD
  Group.
- **Проверяй свой проект так же, как мы.** `MeshGateTierShowcase` в сцене примера `GeneratedTiers.unity` показывает
  каждый ассет пака на каждом уровне с числом треугольников; нажми Play. `python3 meshgate.py check unity` запускает все
  PlayMode-тесты без редактора.
- **Draco, KTX2 и meshopt** требуют своих пакетов Unity; без них отдавай обычный `.glb`.
- **На Android** StreamingAssets лежат внутри APK, поэтому проверка вариантов уровней откатывается к каноническому
  файлу. Задай нужный уровень прямо в `source`.

См. [targets/unity/README.ru.md](../targets/unity/README.ru.md).

### Godot

- **Поставь аддон.** Скопируй `targets/godot/MeshGateDemo/addons/meshgate/` в `res://addons/` и включи его в
  Project → Plugins.
- **Загрузка во время игры.** Узел **MeshGateAsset** с `source` (`res://`, `user://` или абсолютный путь). Он грузит
  через `GLTFDocument`. `MeshGateQuality.apply("mobile-low", get_viewport())` переключает и настройки рендера, и файлы
  уровней.
- **Импорт в редактор** ради коллизий. Только импортёр редактора превращает узлы `-convcolonly` в `StaticBody3D`,
  поэтому положи в проект `.godot.glb` для статичных предметов, которым нужна коллизия.
- **Draco** в Godot 4 не декодируется; отдавай обычный `.glb`. В Godot glTF лучше, чем FBX.

См. [targets/godot/README.ru.md](../targets/godot/README.ru.md).

### Unreal Engine

- **Поставь плагин.** Скопируй `targets/unreal/MeshGate` в `<Project>/Plugins/MeshGate`. Включи **Python Editor Script
  Plugin** и **Interchange** и перезапусти редактор; появится **Tools → MeshGate**.
- **Импорт.** `.glb` идёт через Interchange с настройками конвейера MeshGate. Статичные предметы с коллизией берутся из
  `.unreal.fbx`, его меши `UCX_` становятся коллизией. Персонажи берутся из `.fbx` как Skeletal Mesh.
  `meshgate_import.import_pack(folder, profile="mobile-mid")` заводит целый пак на одном уровне.
- **Качество.** `meshgate_import.apply_quality("mobile-mid")` переводит уровень MeshGate в настройки scalability
  Unreal.
- **Загрузка GLB в собранной игре** — сторонний плагин [glTFRuntime](https://github.com/rdeioris/glTFRuntime) (MIT).
- **Статус.** Каждое имя из API Unreal, которое использует плагин, сверено с UE 5.4–5.6, выбор файлов импортёром пака
  проверен тестом. Живой запуск в редакторе — следующий шаг, поэтому сообщай обо всём, что ведёт себя иначе.

См. [targets/unreal/README.ru.md](../targets/unreal/README.ru.md).

## 7. Если что-то пошло не так

| Признак | Что делать |
|---|---|
| «Blender not found» | Поставь Blender 3.5+ или задай `MESHGATE_BLENDER=/путь/к/blender` |
| «claude is not signed in» | Студия → **«Статус и ИИ»** → **«Войти»**, или один раз `claude auth login` |
| ИИ отвечает без кода | CLI напечатал сообщение вместо кода, обычно о входе или лимите. Оно лежит в `out/gen/<имя>/attempt_1.answer.md` |
| Картинка → 3D: «no generator is ready» | `python3 meshgate.py gen --setup triposr` или задай облачный ключ |
| Сгенерированная сетка наклонена или стоит задом | `--turn 90` поворачивает перёд; `--no-upright` оставляет исходный наклон |
| Цвета от генератора выцвели | Для файлов, где цвет вершин записан значениями картинки, добавь `--vertex-srgb`; файлы TripoSR определяются сами |
| macOS: приложение от неустановленного разработчика | Первый раз нажми правой кнопкой на **MeshGate Studio** → **«Открыть»** (сборки пока не подписаны) |
| Windows SmartScreen блокирует установщик | **«Подробнее» → «Выполнить в любом случае»** |
| Всё остальное | `python3 meshgate.py doctor` и `python3 meshgate.py check all`; в студии **«Статус и ИИ»** показывает, что нашлось; приложение пишет журнал в `~/Library/Logs/dev.meshgate.studio/` или `%LOCALAPPDATA%\dev.meshgate.studio\logs\` |
