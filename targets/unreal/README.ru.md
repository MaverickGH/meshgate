[English](README.md) · **Русский**

# Цель: Unreal Engine 5

Unreal принимает канонический GLB через **Interchange** (UE 5.3+), а FBX — через Interchange (по умолчанию с 5.5) или старый FBX-импортёр; для загрузки в рантайме есть сторонний плагин **glTFRuntime** (MIT). Наша часть — content-only плагин `MeshGate` с Python-скриптами редактора плюс подготовка ассета под Unreal в аддоне Blender.

> **Статус: сверено с Python API Unreal, но ещё не запускалось в живом редакторе.** Unreal на машине разработки не установлен. Вместо этого `python3 meshgate.py check unreal` сверяет каждый класс, метод, значение enum, аргумент конструктора и editor property `unreal.*`, которые использует плагин, со стабами API, которые генерирует сам Unreal для **UE 5.4, 5.5 и 5.6** (публичный пакет [`unreal-stub`](https://pypi.org/project/unreal-stub/)). Разбор первой версии по этим стабам и документации Epic нашёл десяток ошибок — несуществующую функцию диалога, героя вверх ногами (`Rotator` — это roll, pitch, yaw), настройку reference pose, противоречащую контракту, опции FBX, которые UE 5.5+ игнорирует; они исправлены, а проверка не даст этому классу ошибок вернуться. Поведение она не доказывает — первый живой прогон остаётся в роадмапе. Сторона ассета (метры, оси, имена, PBR, скелет, UCX-коллизии) проверена валидатором, тестом аддона на трёх версиях Blender и целями Unity и Godot.

```
targets/unreal/MeshGate/
├── MeshGate.uplugin                       content-only плагин (PythonScriptPlugin, Interchange)
├── Content/Python/init_unreal.py          меню Tools → MeshGate
├── Content/Python/meshgate_import.py      импорт (Interchange / старый FBX), демо-уровень, валидатор
└── Content/Python/meshgate_retarget.md    Humanoid → UE5 Mannequin через IK Rig / IK Retargeter
tests/unreal/check_api.py                  проверка API (Unreal не нужен)
```

![Что плагин делает из каждого файла: GLB → Static Mesh с PBR и клипами; unreal.fbx → Static Mesh с коллизией UCX; FBX персонажа → Skeletal Mesh с ретаргетом на Mannequin; уровень → scalability](../../docs/img/unreal-import.svg)

## Подготовка ассета в Blender

В панели аддона MeshGate включи **Unreal**. Для точных коллизий выдели меши и нажми **Для движков → Добавить коллизию** (выпуклая оболочка или коробка). Экспорт тогда пишет:

- `<name>.glb` — для Interchange (PBR-материалы, анимации, скелеты);
- `<name>.fbx` — для Skeletal Mesh и редакторов, которым удобнее FBX;
- `<name>.unreal.fbx` — если есть прокси коллизий: меши `UCX_<Mesh>_NN`, **дочерние к своему рендер-мешу** (иначе Interchange в UE 5.5 импортирует UCX как видимую геометрию, UE-239476).

![Шары отскакивают от выпуклой оболочки баррикады: меш UCX_ становится её простой коллизией в Unreal](../../docs/img/engine-collision.gif)

## Установка

Скопируй `targets/unreal/MeshGate` в `<Проект>/Plugins/MeshGate`, включи **Python Editor Script Plugin** и **Interchange** (в 5.3+ включён по умолчанию), перезапусти редактор. Появится Tools → MeshGate.

## Как пользоваться

```python
# Python-консоль редактора (Window → Output Log → Cmd: Python)
import meshgate_import
meshgate_import.import_samples("/Users/you/meshgate/samples")   # или задай MESHGATE_SAMPLES; меню тоже его использует
meshgate_import.build_demo_level()                              # /Game/MeshGate/MeshGateDemo, можно запускать повторно
meshgate_import.import_file("/path/asset.glb", "/Game/Props/Asset", skeletal=False)
```

Без интерфейса (коммандлет `pythonscript` не загружает уровни, поэтому `-ExecutePythonScript`):

```bash
UnrealEditor-Cmd Project.uproject -ExecutePythonScript="Plugins/MeshGate/Content/Python/meshgate_import.py --samples /path/samples --level"
```

Что делает импортёр:

| Источник | UE 5.3–5.4 | UE 5.5+ |
|---|---|---|
| `.glb` | Interchange с пайплайном MeshGate | так же |
| `.fbx` / `.unreal.fbx` | старый FBX-импортёр (`FbxImportUI`), если не включён `Interchange.FeatureFlags.Import.FBX` | Interchange с пайплайном MeshGate |

Пайплайн MeshGate — это стандартный assets-пайплайн Epic, продублированный на время импорта, с настройками: меши не склеиваются (`combine_static_meshes = False`), коллизии UCX/UBX/UCP/USP по имени, иначе авто-коллизия, reference pose — bind-поза (`use_t0_as_ref_pose = False`: по контракту rest-поза — T-поза, а кадр 0 — это кадр анимации), анимации, материалы и текстуры включены; для персонажей принудительно skeletal, анимированные пропсы распознаются как rigid skeletal. Свойства, которые переименовывали между релизами (`collision` в 5.5+ против `import_collision` в 5.3/5.4), выставляются по тому имени, которое есть. Каждый исходный файл сначала проходит валидатор MeshGate на Python самого редактора.

`build_demo_level()` открывает уровень, если он есть (иначе создаёт), один раз добавляет солнце и небесный свет, заменяет ранее расставленные актёры MeshGate и расставляет все импортированные примеры в той же раскладке, что web/Unity/Godot; герой смотрит в камеру (`Rotator(roll=0, pitch=0, yaw=180)`).

## Контракт → Unreal: что важно знать

- **Единицы.** UE — сантиметры, Z-up, левосторонняя система. Interchange и FBX-импортёр переводят метры → см и Y-up → Z-up; наш FBX пишет `UnitScaleFactor = 100`, поэтому «Import Uniform Scale» остаётся 1.0. `LAYOUT` в скрипте — в сантиметрах.
- **Иерархия.** Меши не склеиваются, `crate_lid` остаётся отдельным Static Mesh. `import_asset` создаёт только ассеты; расстановка целой сцены с актёрами — это `import_scene` (пока не используется).
- **Материалы.** GLB → Interchange даёт PBR-инстансы материалов (metallic/roughness-карты, эмиссия, прозрачность). FBX → только albedo/normal/emissive (см. `docs/asset-contract.ru.md`).
- **Анимации.** `AnimSequence` по имени клипа (`lid_open`, `wave` …). Клип на несколько объектов (`rotors` у дрона) в FBX — это несколько take; используйте GLB.
- **Humanoid.** Кости с именами Unity Humanoid → цепочки IK Rig сопоставляются по имени; ретаргет на UE5 Mannequin — `meshgate_retarget.ru.md`.
- **LOD.** Unreal строит LOD сам (LOD Group при импорте). Меши `_LODn` из аддона — только для Unity; UE читает LOD лишь из узлов LOD Group в FBX, а Blender их не пишет.
- **Draco / KTX2** — Interchange их не читает; используйте несжатый GLB.

## Рантайм: glTFRuntime

Загрузка GLB в собранной игре — [glTFRuntime](https://github.com/rdeioris/glTFRuntime) (MIT, Fab/GitHub). Рецепт на Blueprint:

1. `glTFLoadAssetFromFilename` (пакуйте `Content/MeshGate/*.glb` как «Additional Non-Asset Directories»).
2. `Load Static Mesh by Name` для пропсов (`crate_body`, `barrel_body`) или `Get Nodes` → для каждой ноды `Load Static Mesh` + `Spawn Actor` с `Node Transform` — сохраняет иерархию и имена по контракту.
3. Персонажи: `Load Skeletal Mesh Recursive` (`hero_body`) → `Load Skeletal Animation by Name` (`wave`) → `Play Animation`.
4. Наведение/клик — `LineTraceByChannel` от камеры; подсветка — `Set Render Custom Depth` + post-process-материал.

C++-версия `MeshGateAsset` поверх glTFRuntime с тем же API, что в Unity/Godot, — после первого живого прогона.
