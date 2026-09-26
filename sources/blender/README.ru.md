[English](README.md) · **Русский**

# MeshGate для Blender

Аддон для Blender: проверяет сцену по [контракту ассета](../../docs/asset-contract.ru.md), в один клик исправляет то, что можно исправить автоматически, и экспортирует проверенный GLB (плюс FBX и варианты под конкретные движки) для веба, Unity, Godot и Unreal.

Работает в **Blender 3.5 – 5.x** из одного zip (проверено на 3.5, 4.2 LTS и 5.2 LTS командой `python3 meshgate.py check blender`).

<img src="../../docs/img/blender-panel.png" alt="Панель MeshGate в Blender 5.2: цели, Проверить / Исправить всё / Экспорт, отчёт валидатора" width="320" align="right">

## Установка

**А. Одной командой** (есть этот репозиторий и Python 3):

```bash
python3 meshgate.py install-blender              # соберёт zip, установит и включит аддон в твоём Blender
python3 meshgate.py install-blender --all        # во все Blender на этой машине
python3 meshgate.py install-blender --uninstall  # удалить обратно
```

Сначала закрой Blender — запущенный Blender при выходе сохраняет свои настройки и отменит установку. Перед изменениями `userpref.blend` копируется рядом как резервная копия. Blender ищется в обычных местах; иначе укажи `--blender /путь/к/blender` или задай `MESHGATE_BLENDER`.

**Б. Вручную** (только zip, Python не нужен):

1. Скачай `meshgate-blender-<версия>.zip` со страницы релизов (или собери: `python3 meshgate.py addon` → `dist/`).
2. Blender **4.2+**: перетащи zip в окно Blender (или Edit → Preferences → Get Extensions → ⌄ → Install from Disk).
   Blender **3.5–4.1**: Edit → Preferences → Add-ons → Install… → выбери zip → поставь галочку **MeshGate**.

Дальше: 3D-вид → клавиша **N** → вкладка **MeshGate** (ещё есть File → Export → MeshGate).

Русский интерфейс: Preferences → Interface → Translation → Русский (галочка «Interface»).

## Как пользоваться

1. **Цели.** Включи Web / Unity / Godot / Unreal. Выбери папку экспорта (`//export/` — рядом с .blend) и имя.
2. **Проверить.** Покажет все нарушения контракта: единицы, размер, неприменённый или отрицательный масштаб, имена с пробелами или кириллицей, меши без UV или материала, материалы без PBR, отсутствующие / внешние / не степени двойки / слишком большие текстуры, ассет ниже пола, скелет Mixamo/Rigify/UE, который можно переименовать в Unity Humanoid, вершины без весов, свободные действия рядом с NLA-клипами.
3. **Исправить** рядом с проблемой или **Исправить всё** (Ctrl+Z откатывает). Что чинится: метры, применение масштаба, транслитерация и чистка имён, Smart UV-развёртка, PBR-материал по умолчанию, упаковка текстур, приведение к степени двойки (≤ 4096), постановка ассета на Z = 0, переименование костей в Unity Humanoid, привязка «потерянных» вершин к ближайшей кости и нормализация (≤ 4 на вершину), перенос действий в NLA. Запекание процедурных материалов остаётся за тобой.
4. **Экспорт.** Пишет файлы из таблицы ниже и прогоняет валидатор по каждому; отчёт появляется в панели. **Открыть в браузере** раздаёт папку прямо из Blender на localhost и открывает веб-вьюер MeshGate (нужен интернет — Three.js грузится с CDN).

| Файл | Когда | Для чего |
|---|---|---|
| `<name>.glb` | всегда | канонический ассет: веб, Unity (glTFast), Godot, Unreal (Interchange) |
| `<name>.draco.glb` | Web + «Draco для веба» | меньше вес для веба; Godot/Unreal его не читают |
| `<name>.fbx` | «Ещё и FBX», Unity или Unreal | редакторы движков, Unity Humanoid / UE Skeletal Mesh |
| `<name>.unity.fbx` | Unity + в сцене есть LOD | меши `_LOD0.._LODn` → Unity собирает LODGroup |
| `<name>.unreal.fbx` | Unreal + в сцене есть коллизии | коллизии `UCX_<меш>_NN` → Unreal берёт их вместо авто-коллизии |
| `<name>.godot.glb` | Godot + в сцене есть коллизии | ноды `<меш>…-convcolonly` → Godot создаёт StaticBody3D с выпуклой формой |

**Для движков** (подпанель): **Добавить коллизию** создаёт скрытый прокси — выпуклую оболочку или коробку — для каждого выделенного меша; **Сделать LOD** создаёт скрытые упрощённые копии (50 % и 25 %). В канонический GLB они не попадают — только в тот вариант, которому нужны.

## Без интерфейса (тот же код)

```bash
blender -b scene.blend -P sources/blender/export_meshgate.py -- --out build/asset.glb \
        --targets web,unity,godot,unreal --fbx --check --fix --validate
python3 meshgate.py export scene.blend --out build/asset.glb --fbx      # CLI оборачивает строку выше
```

`--check` печатает проблемы, `--fix` применяет все автоматические исправления перед экспортом (`--save-fixed out.blend` сохраняет результат), `--validate` возвращает 1, если хоть один файл нарушает контракт.

## Разработка

- Код: `sources/blender/meshgate_blender/` — `checks.py` (правила + исправления), `export.py` (канонический файл + варианты + проверка), `tools.py` (коллизии, LOD, превью), `ui.py` (панель/операторы), `compat.py` (различия API Blender 3.5 → 5.x), `translations.py`.
- Проверка на всех установленных Blender: `python3 meshgate.py check blender`. Для каждой версии ставит zip во временный профиль (твои настройки Blender не трогаются), подкладывает в сцену все проблемы, проверяет, что «Проверить» их находит, а «Исправить всё» убирает, экспортирует все варианты и заглядывает внутрь, пересобирает демо-ассеты. Дополнительные сборки Blender клади в `~/.cache/meshgate/blender/` или перечисли в `MESHGATE_BLENDERS`.
