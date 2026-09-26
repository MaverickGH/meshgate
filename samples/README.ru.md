[English](README.md) · **Русский**

# Примеры

| Файл | Что это |
|---|---|
| `meshgate_demo.blend` | Исходник демо-ассета «сундук с маяком» (Blender 3.5+, текстуры запакованы). Генерируется скриптом `sources/blender/make_demo_scene.py`. |
| `meshgate_demo.glb` | Канонический GLB по контракту: 17 мешей, 4 PBR-материала, 2 текстуры 1024², 2 анимации (`lid_open`, `beacon_spin`). |
| `meshgate_demo.draco.glb` | Тот же ассет со сжатием Draco — для проверки декодеров в рантаймах. |
| `meshgate_hero.blend` / `.glb` / `.fbx` | Демо-персонаж: гладкий манекен 1.75 м (voxel remesh), скелет из 21 кости с именами Unity Humanoid, веса, UV-развёртка, 3 материала, анимации `idle` и `wave` на костях. Генерируется `sources/blender/make_demo_character.py`. FBX импортируется в Unity как Humanoid-аватар. |
| `meshgate_lantern.*` | Фонарь: стекло с `KHR_materials_transmission`/`ior`, эмиссия пламени, цепь; анимации `swing` (качание вокруг точки подвеса) и `flicker` (масштаб пламени). |
| `meshgate_barrel.*` | Бочка: процедурные albedo-, normal- (из карты высот) и roughness-карты, цилиндрическая развёртка, без анимаций. |
| `meshgate_drone.*` | Дрон: глубокая иерархия (корпус → лучи → моторы → роторы → лопасти), клипы `hover` и `rotors` (один клип на 4 объекта), 90 КБ. |
| `packs/zombie_cats/` | Пример пака **Коты-зомби**: 11 стилизованных ассетов + диорама, один материал-палитра, варианты с коллизиями, кот-зомби на Humanoid — см. [его README](packs/zombie_cats/README.ru.md). |
| `packs/generated/` | Пример пака **Сгенерированное**: шесть ассетов, сделанных `meshgate.py gen`, — код набора по тексту и по картинке и сетка TripoSR по картинке, у каждого четыре уровня качества. См. [его README](packs/generated/README.ru.md). |
| `index.json` | Список примеров для галереи веб-вьюера. |
| `meshgate_demo.fbx` | Запасной путь для редакторов Unity/Unreal: метры, Y-up, 2 take, текстуры встроены. Получается тем же экспортом с флагом `--fbx`; проверка — `core/validate_fbx.py`. |

Ассет специально устроен как «настоящий» игровой пропс: иерархия (`meshgate_demo → crate_body → crate_lid → beacon_post → beacon_ring`), origin в основании, крышка вращается вокруг петли, маяк — дочерний объект крышки и едет вместе с ней, есть эмиссия (`KHR_materials_emissive_strength`) и прозрачное стекло. Это ловит типичные ошибки адаптеров: потерю иерархии, неверные оси, анимации на дочерних нодах, прозрачность.

## Пересобрать

```bash
BLENDER=/Applications/Blender.app/Contents/MacOS/Blender   # macOS; в Linux обычно просто `blender`
$BLENDER -b -P sources/blender/make_demo_scene.py -- --blend samples/meshgate_demo.blend
$BLENDER -b samples/meshgate_demo.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_demo.glb --fbx --validate   # + meshgate_demo.fbx
$BLENDER -b -P sources/blender/make_demo_character.py -- --blend samples/meshgate_hero.blend
$BLENDER -b -P sources/blender/make_demo_props.py -- --out-dir samples                       # lantern, barrel, drone
for n in hero lantern barrel drone; do $BLENDER -b samples/meshgate_$n.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_$n.glb --fbx --validate; done
$BLENDER -b samples/meshgate_demo.blend -P sources/blender/export_meshgate.py -- --out samples/meshgate_demo.draco.glb --draco --validate
```

## Свой персонаж (реалистичный аватар, Mixamo, Rigify, UE Mannequin)

```bash
$BLENDER -b -P sources/blender/animate_humanoid.py -- --in ~/Downloads/avatar.glb --blend samples/_local/avatar.blend
$BLENDER -b samples/_local/avatar.blend -P sources/blender/export_meshgate.py -- --out samples/_local/avatar.glb --fbx --validate
```

`animate_humanoid.py` находит кости Humanoid по именам (Unity / Mixamo / Rigify / UE), приводит к метрам и origin в ногах, добавляет `idle` и `wave`, если своих анимаций нет. Папка `samples/_local/` игнорируется git — для чужих ассетов с неясной лицензией.

Свои `.glb`/`.blend` в этой папке игнорируются git — кладите их сюда для локальных проверок без риска раздуть репозиторий.
