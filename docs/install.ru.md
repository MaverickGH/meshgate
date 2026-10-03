[English](install.md) · **Русский**

# Установка

Всё, что нужно MeshGate, по шагам, для macOS, Windows и Linux. Обязательны только шаги 1–3; остальные добавляют то,
что ты хочешь делать. В конце — [проверка всего](#8-проверить-что-всё-работает) в одном месте.

| Хочешь… | Нужно | Шаг |
|---|---|---|
| Открыть MeshGate Studio | Приложение (Windows включает Python) или переносной архив | [1](#1-meshgate-studio), [2](#2-python) |
| Собирать, проверять и экспортировать модели | **Blender 3.5+** с аддоном MeshGate | [3](#3-blender-и-аддон-meshgate) |
| Делать модель по описанию | Один **ИИ-инструмент командной строки**, один вход | [4](#4-ии-инструмент-для-текст--3d) |
| Делать модель по картинке | **TripoSR** (локально, бесплатно) или облачный ключ | [5](#5-картинка--3d) |
| Класть файлы в движок | Плагин MeshGate для Unity, Godot или Unreal | [6](#6-плагины-для-движков) |
| Лучше картинка → 3D, анимации персонажей | Дополнительные компоненты (видеокарта NVIDIA) | [7](#7-дополнительные-компоненты) |

## Как это работает

Ты описываешь модель или бросаешь картинку в MeshGate Studio. ИИ-инструмент пишет короткую программу, которая
собирает модель из простых деталей (*движок kit*), или нейросеть превращает картинку в сетку (*движок mesh*).
Blender в фоне собирает модель отдельно для каждого уровня качества — PC, mobile high, mobile mid, mobile low —
проверяет каждый файл по бюджету уровня и правилам движков и отправляет найденные проблемы ИИ на исправление. На выходе
по одному проверенному `.glb` на уровень плюс `.fbx` и варианты для движков, в 3D прямо в студии и в твоей библиотеке.

![текст → код → Blender по уровням → проверенные файлы](img/generation-flow.svg)

MeshGate работает на твоём компьютере. Студия — небольшой локальный сервер с окном; наружу уходит только то, что нужно
выбранному тобой ИИ-инструменту или облачному генератору.

## 1. MeshGate Studio

Скачай со страницы [Releases](https://github.com/MaverickGH/meshgate/releases):

| Система | Файл | Установка |
|---|---|---|
| macOS (Apple Silicon) | `MeshGate.Studio_<версия>_aarch64.dmg` | Открой и перетащи **MeshGate Studio** в «Программы» |
| Windows 10/11 (64-бит) | `MeshGate.Studio_<версия>_x64-setup.exe` или `_x64_en-US.msi` | EXE: для текущего пользователя, без администратора. MSI: для компьютера, нужен администратор |
| Linux или любая система без установки | `MeshGate-<версия>-portable.zip` | Распакуй куда угодно |

Сборки пока не подписаны, поэтому при первом запуске нужен один лишний клик:

- **macOS:** правой кнопкой по **MeshGate Studio** → **«Открыть»** → **«Открыть»**. На macOS 15 и новее, если всё
  равно не открывается: Системные настройки → Конфиденциальность и безопасность → **«Всё равно открыть»**.
- **Windows:** SmartScreen → **«Подробнее»** → **«Выполнить в любом случае»**.

Переносную версию запускай из её папки (то же написано в `START.txt` внутри):

```bash
python3 meshgate.py studio
```

Студия откроется в браузере. Она работает только на этом компьютере, снаружи к ней не подключиться.
На Windows можно запустить `START_WINDOWS.cmd` двойным кликом: он ищет Python через `py -3`, `python` или `python3`.
При необходимости задай `MESHGATE_PYTHON` — полный путь к исполняемому файлу Python.

**Из исходников** (для разработки): `git clone https://github.com/MaverickGH/meshgate.git`, затем
`python3 meshgate.py studio` в этой папке.

Для Windows без установки скачай `MeshGate-<версия>-windows-portable.zip`, распакуй и запусти `START_WINDOWS.cmd`.
Python и uv уже в архиве.

Порядок первого запуска на Windows 10/11 x64:

1. Установи MeshGate через EXE и открой его из меню «Пуск». Build Tools, Node.js, Git и системный Python для окна Studio не нужны.
2. Установи Blender с официального сайта; перезапусти Studio и проверь зелёный индикатор Blender.
3. Для картинки → 3D открой «Статус и ИИ» → TripoSR → «Установить». Интернет нужен для установки пакетов и первой загрузки весов; затем модель работает локально.
4. Для текста → 3D выбери один ИИ-инструмент и войди в свой аккаунт. Облачные инструменты требуют аккаунта/ключа; Ollama — отдельной локальной модели.
5. Загрузи картинку и запусти генерацию. Файлы появятся в «Документы/MeshGate Assets».

Для локальных моделей Windows также нужен [Microsoft Visual C++ Redistributable x64](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist). Studio проверит его перед установкой TripoSR и покажет ссылку на официальный установщик, если компонента нет. Build Tools не нужны.

## 2. Python

MeshGate Studio работает на **Python 3.9 или новее**. В Windows x64 установщик и `-windows-portable.zip` включают
собственные Python и uv — отдельно устанавливать Python не нужно. На других системах и для обычного `-portable.zip`
Python ставится отдельно. Сервер использует стандартную библиотеку, дополнительных пакетов для запуска не нужно.

- **macOS:** обычно уже есть. Если нет — поставь с [python.org](https://www.python.org/downloads/) или выполни
  `xcode-select --install` в Терминале.
- **Windows:** установщик уже включает Python. Для исходников или обычного переносного архива поставь Python с
  [python.org](https://www.python.org/downloads/) и отметь **Add python.exe to PATH**.
- **Linux:** стоит в большинстве дистрибутивов (`python3 --version`).

Если приложение пишет, что Python не найден, — поставь его и открой приложение снова. `MESHGATE_PYTHON` указывает
конкретный Python.

## 3. Blender и аддон MeshGate

1. Поставь **Blender 3.5 или новее** с [blender.org](https://www.blender.org/download/). MeshGate проверен на 3.5,
   4.2 LTS и 5.2 LTS.
2. MeshGate сам находит Blender в обычных местах: «Программы» на macOS, Program Files или Steam на Windows,
   `/usr/bin`, `/snap/bin`, `/opt` или распакованный в домашнюю папку архив на Linux. В других местах задай
   `MESHGATE_BLENDER` — путь к исполняемому файлу Blender.
3. Поставь аддон при закрытом Blender — любым способом:
   - студия → **«Статус и ИИ»** → Blender → **«Поставить аддон»**;
   - `python3 meshgate.py install-blender`;
   - вручную: `python3 meshgate.py addon` пишет `dist/meshgate-blender-<версия>.zip`. Blender 4.2+: перетащи zip в
     окно Blender. Blender 3.5–4.1: Preferences → Add-ons → Install.
4. В Blender нажми **N** → вкладка **MeshGate**: **«Проверить»**, **«Исправить всё»**, **«Экспорт»**. См.
   [sources/blender/README.ru.md](../sources/blender/README.ru.md).

Студии Blender нужен для каждой сборки, а аддон — нет: он для работы в самом Blender.

## 4. ИИ-инструмент для текст → 3D

Для текст → 3D нужен один ИИ-инструмент командной строки. Студия → **«Статус и ИИ»** показывает состояние каждого,
ставит его в окне терминала и запускает вход. То же вручную:

| Инструмент | Установка | Войти один раз |
|---|---|---|
| [Claude Code](https://docs.claude.com/en/docs/claude-code) | `npm install -g @anthropic-ai/claude-code` | `claude auth login`, или задай `ANTHROPIC_API_KEY` |
| [Codex CLI](https://github.com/openai/codex) | `npm install -g @openai/codex` | `codex login`, или задай `OPENAI_API_KEY` |
| [Gemini CLI](https://github.com/google-gemini/gemini-cli) | `npm install -g @google/gemini-cli` | запусти `gemini` и выбери вход, или задай `GEMINI_API_KEY` |
| [Ollama](https://ollama.com/download), без интернета | приложение с ollama.com | `ollama pull qwen2.5-coder:14b` |

`npm` идёт вместе с [Node.js](https://nodejs.org) 18 или новее. Хватает входа по подписке (Claude, ChatGPT для Codex,
Google для Gemini); API-ключ — альтернатива. Codex со входом через ChatGPT ещё и бесплатно рисует картинки-концепты
(`--concept sheet`, галочка в студии «Сначала нарисовать концепт»).

## 5. Картинка → 3D

Выбери одно:

- **TripoSR — локально и бесплатно** (MIT, процессор, NVIDIA CUDA или видеочип Apple; CUDA занимает больше места). Студия → **«Статус и ИИ»** →
  «Дополнительные компоненты» → TripoSR → **«Установить»** (есть и в разделе «Нейросеть и дополнительно»), или
  `python3 meshgate.py gen --setup triposr`. Нужен [uv](https://docs.astral.sh/uv/) либо Python 3.10–3.12; Windows-сборка включает их. Git необязателен: без него установщик скачает и проверит закреплённый архив исходников.
  Windows автоматически выбирает CUDA для совместимых NVIDIA с подходящим драйвером, иначе CPU. Чтобы задать вручную проверенную конфигурацию GTX 1080: перед установкой задать `MESHGATE_TRIPOSR_TORCH_SPEC=torch==2.7.1`
  и `MESHGATE_TRIPOSR_TORCH_INDEX=https://download.pytorch.org/whl/cu118`.
  `MESHGATE_TRIPOSR_HOME` задаёт папку окружения; `MESHGATE_TRIPOSR_MODEL` может указывать на локальную папку
  с `config.yaml` и `model.ckpt`. Используй одинаковые `HF_HOME` и `U2NET_HOME` при установке и запуске,
  чтобы конфигурация трансформера и модель удаления фона использовались из кэша без сети.
- **Облачный генератор:** ключ [Meshy](https://www.meshy.ai/api) (`MESHY_API_KEY`), [Tripo](https://platform.tripo3d.ai)
  (`TRIPO_API_KEY`) или [fal.ai](https://fal.ai/dashboard/keys) (`FAL_KEY`: TRELLIS, Hunyuan3D, TripoSR). Вставь его в
  студии → **«Статус и ИИ»** → «Ключи API» или задай в окружении.

Ключи лежат в `~/.meshgate/keys.json`, файл читаешь только ты; студия показывает лишь последние четыре символа.

## 6. Плагины для движков

Студия → **«Статус и ИИ»** показывает, какие движки установлены, и открывает папку каждого плагина
(**«Файлы плагина»**).

- **Web (Three.js):** ставить ничего не нужно. Раздавай файлы `.glb` и используй
  [`targets/web/meshgate-viewer.js`](../targets/web/README.ru.md), или `python3 meshgate.py serve --glb file.glb`.
- **Unity 6000.0+:** поставь **glTFast** (`com.unity.cloud.gltfast`) из реестра Unity. Затем Package Manager →
  **Add package from disk** → `package.json` в папке плагина (`targets/unity/com.meshgate.unity`), или **Add package
  from git URL** → `https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity`.
  См. [targets/unity/README.ru.md](../targets/unity/README.ru.md).
- **Godot 4.4+:** скопируй `targets/godot/MeshGateDemo/addons/meshgate/` в `res://addons/` своего проекта и включи в
  Project → Plugins. См. [targets/godot/README.ru.md](../targets/godot/README.ru.md).
- **Unreal Engine 5.4–5.6:** скопируй `targets/unreal/MeshGate` в `<Project>/Plugins/`, включи **Python Editor Script
  Plugin** и **Interchange**, перезапусти; появится **Tools → MeshGate**. См.
  [targets/unreal/README.ru.md](../targets/unreal/README.ru.md).

Какой файл куда и рекомендации по каждому движку: [С чего начать §5–6](getting-started.ru.md#5-какие-файлы-пишет-meshgate).

## 7. Дополнительные компоненты

Большие локальные модели, ставятся только когда нужны — студия → **«Статус и ИИ»** → «Дополнительные компоненты», или
командой. Каждый получает свою папку и своё окружение Python в `~/.cache/meshgate`; нужны `git` и
[uv](https://docs.astral.sh/uv/).

| Компонент | Для чего | Установка | Нужно | Лицензия |
|---|---|---|---|---|
| Hunyuan3D-2 | Картинка → 3D с более точной формой | `meshgate.py gen --setup hunyuan3d` (~10 ГБ) | Видеокарта NVIDIA от 6 ГБ (от 16 ГБ с текстурами) | Tencent Hunyuan 3D Community License — не в ЕС, Великобритании и Южной Корее |
| Kimodo | Текст → анимация персонажей Humanoid | `meshgate.py gen --setup kimodo` (~20 ГБ) | Видеокарта NVIDIA; доступ к Meta Llama 3 8B на Hugging Face, затем `hf auth login` | код Apache-2.0, NVIDIA Open Model License; Llama 3 Community License |

Оба уже ставятся; генерация начнёт ими пользоваться после проверенного прогона на подходящей видеокарте
([роадмап](roadmap.ru.md)).

## 8. Проверить, что всё работает

- **В студии:** кнопки в шапке показывают, что найдено; **«Статус и ИИ»** перечисляет Blender с аддоном, Unity, Godot,
  Unreal, ИИ-инструменты с состоянием входа, генераторы картинок, дополнительные компоненты и ключи — у каждого
  написано, что сделать дальше.
- **В терминале:** `python3 meshgate.py doctor` печатает то же и в конце пишет следующие шаги.
- **Первая модель:** напиши «деревянный ящик с металлическими уголками» и нажми **«Сгенерировать»**. Сборка занимает
  одну–три минуты; каждый уровень появится в 3D с числом треугольников.

## Где MeshGate хранит данные

| Что | Где |
|---|---|
| Твои модели (библиотека студии) | `~/Documents/MeshGate Assets` (из исходников — `out/gen`); **«Показать файлы»** открывает папку модели |
| Ключи API | `~/.meshgate/keys.json` |
| TripoSR, Hunyuan3D, Kimodo | `~/.cache/meshgate/<имя>` |
| Журнал приложения | macOS `~/Library/Logs/dev.meshgate.studio/`, Windows `%LOCALAPPDATA%\dev.meshgate.studio\logs\` |

**Обновление:** поставь новый релиз поверх старого; библиотека, ключи и компоненты останутся. **Удаление:** удали
приложение (или папку переносной версии), затем при желании — папки выше.

Что-то не работает? [С чего начать → Если что-то пошло не так](getting-started.ru.md#7-если-что-то-пошло-не-так).
