[English](README.md) · **Русский**

# Пример пака: Коты-зомби

Набор для милого апокалипсиса — 11 ассетов и диорама — целиком построенный одним скриптом Blender и прогнанный через весь пайплайн MeshGate: проверка контракта внутри Blender, экспорт с вариантами для движков, валидатор, веб-вьюер, Unity, Godot и Unreal. Это и витрина, и тест: `python3 meshgate.py check blender` пересобирает его на каждой версии Blender, а тесты Unity и Godot грузят каждый ассет и сверяют с этим `index.json`.

![Коты-зомби в Unity: диорама, кот-зомби в рантайме, FBX-кот как Humanoid и герой с кошачьей походкой](../../../docs/img/pack-zombie-cats-unity.png)

## Как устроен (так делают настоящие стилизованные паки)

- **Одна текстура-палитра** (`zc_palette`, 256², 29 цветовых клеток) и **один PBR-материал** (`zc_atlas`) на весь пак; каждая грань берёт плоский цвет из клетки с nearest-фильтрацией. Светящиеся части — `zc_glow` / `zc_lamp`. Пропс — один меш с одним-двумя материалами, то есть один-два draw call.
- Каждый пропс стоит origin'ом на земле, в метрах, с ASCII-именами.
- У статичных пропсов есть **прокси коллизий**: в `<name>.unreal.fbx` — выпуклые меши `UCX_`, в `<name>.godot.glb` — ноды `-convcolonly` (Godot при импорте превращает их в StaticBody3D).
- **`zc_zombie_cat`** — двуногий персонаж на скелете **Unity Humanoid** плюс три кости хвоста, жёсткая голова, веса по ближайшей кости, клипы `idle` и `shamble`. Его FBX импортируется в Unity как валидный Humanoid-аватар, поэтому походку можно перенести на любого другого гуманоида (см. героя на картинке).
- **`zc_diorama`** — улица 8 × 8 м из связанных дубликатов: инстансы плиток и заборов, три шаркающих кота, фонари, могилы, токсичная банка.

## Ассеты

| Файл | Ассет | Трис | Размер, м (X×Y×Z, Y вверх) | Клипы | Кости | Варианты для движков |
|---|---|---|---|---|---|---|
| `zc_ground_tile.glb` | Плитка земли (следы лап) | 606 | 2.00×0.04×2.00 | — | — | — |
| `zc_road_tile.glb` | Плитка дороги (разметка-рыбки) | 308 | 2.00×0.10×2.00 | — | — | — |
| `zc_fence_broken.glb` | Сломанный забор (штакетник с ушками) | 1,188 | 2.00×1.10×0.77 | — | — | zc_fence_broken.unreal.fbx, zc_fence_broken.godot.glb |
| `zc_tombstone_cat.glb` | Надгробие-кот | 768 | 0.70×1.08×0.40 | — | — | zc_tombstone_cat.unreal.fbx, zc_tombstone_cat.godot.glb |
| `zc_dead_tree.glb` | Мёртвое дерево + клубок | 304 | 1.28×2.47×1.15 | yarn_swing | — | zc_dead_tree.unreal.fbx, zc_dead_tree.godot.glb |
| `zc_cardboard_barricade.glb` | Баррикада из коробок (в ней прячется кот) | 772 | 1.82×1.23×0.69 | — | — | zc_cardboard_barricade.unreal.fbx, zc_cardboard_barricade.godot.glb |
| `zc_toxic_can.glb` | Токсичная банка кошачьего корма | 1,132 | 0.99×1.01×0.73 | bubbles | — | zc_toxic_can.unreal.fbx, zc_toxic_can.godot.glb |
| `zc_street_lamp.glb` | Фонарь-рыба | 780 | 1.27×3.17×0.36 | swing | — | zc_street_lamp.unreal.fbx, zc_street_lamp.godot.glb |
| `zc_bones_pile.glb` | Рыбьи кости | 282 | 0.66×0.07×0.47 | — | — | — |
| `zc_scratch_post_ruin.glb` | Разрушенная когтеточка | 1,320 | 1.09×1.15×0.80 | — | — | zc_scratch_post_ruin.unreal.fbx, zc_scratch_post_ruin.godot.glb |
| `zc_zombie_cat.glb` | Кот-зомби (Humanoid, idle/shamble) | 4,520 | 0.81×1.05×0.48 | idle, shamble | 24 | — |
| `zc_diorama.glb` | Диорама: улица котов-зомби | 21,020 | 8.60×3.20×9.19 | bubbles, idle, shamble, swing, yarn_swing | 72 | — |

У каждого ассета есть и `<name>.fbx` (кроме диорамы). Все файлы проходят контракт со `--strict`.

## Пересобрать

```bash
blender -b -P sources/blender/make_pack_zombie_cats.py -- --out-dir samples/packs/zombie_cats
python3 meshgate.py samples            # пересоберёт пак вместе с остальными примерами
```

Или открой `zombie_cats.blend` в Blender с аддоном MeshGate: каждый ассет — отдельная коллекция; выдели её и нажми **Экспорт**.

## Как использовать

- **Веб:** `python3 meshgate.py serve` → в галерее есть группа «Zombie Cats pack».
- **Unity:** `MeshGateSampleTools.BuildAll` копирует пак и собирает `Assets/MeshGate/ZombieCatsDemo.unity`; `MeshGateAsset` с `playOnLoad = "shamble"` заставляет кота идти в рантайме.
- **Godot:** `targets/godot/sync_samples.sh`, затем открой `demo_pack.tscn` (диорама с `play_on_load = "shamble"` и забор с коллизией).
- **Unreal:** `meshgate_import.import_pack("/path/samples/packs/zombie_cats")` — `.unreal.fbx` с UCX для статичных пропсов, иначе GLB, кот — как Skeletal Mesh.

![Коты-зомби в Godot 4 с проигрываемым клипом shamble](../../../docs/img/pack-zombie-cats-godot.png)
