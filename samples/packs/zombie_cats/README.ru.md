[English](README.md) · **Русский**

# Пример пака: Коты-зомби

Набор для милого апокалипсиса — 11 ассетов и диорама — из стилизованных моделей kit стилей Котов-зомби (верхний ряд
[линейки стилей](../../../docs/img/zc-styles-lineup.jpg), по концепт-арту), прогнанный через весь пайплайн MeshGate:
все уровни качества, прокси коллизий, варианты для движков, валидатор, веб-вьюер, Unity, Godot и Unreal. Это и витрина,
и тест: `python3 meshgate.py check blender` пересобирает его на каждой версии Blender, а тесты Unity и Godot грузят
каждый ассет и сверяют с этим `index.json`.

![Коты-зомби в Unity: диорама, кот-зомби в рантайме, FBX-кот как Humanoid и герой с кошачьей походкой](../../../docs/img/pack-zombie-cats-unity.png)

## Как устроен

- Каждый ассет — **код kit** (`sources/generate/examples/zombie_cats/stylized/*.py`), который `meshgate.py gen` собирает
  на каждом уровне: pc — канонический файл, `<имя>.mobile-low/mid/high.glb` собираются заново с детализацией уровня, а не
  просто прореживаются, и укладываются в его бюджет.
- **Один материал-палитра** на ассет (базовый цвет, шероховатость-металл, свечение) — один draw call на меш.
- Каждый пропс стоит origin'ом на земле, в метрах, с ASCII-именами.
- У статичных пропсов есть **прокси коллизий**: в `<имя>.unreal.fbx` — меши `UCX_`, в `<имя>.godot.glb` — ноды
  `-convcolonly` (Godot при импорте превращает их в StaticBody3D).
- **`zc_zombie_cat`** — риг на скелете **Unity Humanoid** плюс кости хвоста, клипы `idle` и `shamble`.
- **`zc_diorama`** — улица 8 × 8 м из связанных дубликатов: инстансы плиток и заборов, три шаркающих кота, фонари,
  могилы, токсичная банка; её файлы уровней укладываются в бюджет сцены каждого уровня.

## Ассеты

| Файл | Ассет | Трис, mobile-low → PC | Размер, м (X×Y×Z, Y вверх) | Клипы | Кости | Варианты для движков |
|---|---|---|---|---|---|---|
| `zc_ground_tile.glb` | Плитка земли (следы лап) | 1 094 → 5 741 | 2.00×0.05×2.00 | — | — | — |
| `zc_road_tile.glb` | Плитка дороги (рыбьи метки) | 67 → 758 | 2.00×0.11×2.00 | — | — | — |
| `zc_fence_broken.glb` | Сломанный забор | 1 354 → 4 943 | 1.95×1.10×0.23 | — | — | zc_fence_broken.unreal.fbx, zc_fence_broken.godot.glb |
| `zc_tombstone_cat.glb` | Кошачье надгробие | 760 → 10 244 | 0.82×1.08×0.64 | — | — | zc_tombstone_cat.unreal.fbx, zc_tombstone_cat.godot.glb |
| `zc_dead_tree.glb` | Мёртвое дерево и клубок | 371 → 2 336 | 1.58×2.61×0.89 | yarn_swing | — | zc_dead_tree.unreal.fbx, zc_dead_tree.godot.glb |
| `zc_cardboard_barricade.glb` | Баррикада из коробок (кот прячется) | 680 → 8 879 | 1.84×1.33×0.67 | — | — | zc_cardboard_barricade.unreal.fbx, zc_cardboard_barricade.godot.glb |
| `zc_toxic_can.glb` | Токсичная банка кошачьего корма | 2 125 → 20 776 | 1.00×1.26×1.15 | bubbles | — | zc_toxic_can.unreal.fbx, zc_toxic_can.godot.glb |
| `zc_street_lamp.glb` | Уличный фонарь-рыба | 294 → 8 218 | 0.56×3.15×0.96 | swing | — | zc_street_lamp.unreal.fbx, zc_street_lamp.godot.glb |
| `zc_bones_pile.glb` | Рыбьи кости | 923 → 7 324 | 0.67×0.20×0.25 | — | — | — |
| `zc_scratch_post_ruin.glb` | Разрушенная когтеточка | 2 338 → 25 831 | 0.81×1.16×0.57 | — | — | zc_scratch_post_ruin.unreal.fbx, zc_scratch_post_ruin.godot.glb |
| `zc_zombie_cat.glb` | Кот-зомби (Humanoid, idle/shamble) | 2 268 → 44 086 | 0.48×1.09×0.62 | idle, shamble | 25 | — |
| `zc_diorama.glb` | Диорама: улица котов-зомби | 50 636 → 360 983 | 8.00×3.15×8.00 | bubbles, idle, shamble, swing, yarn_swing | 75 | — |

У каждого ассета есть ещё `<имя>.fbx` (кроме диорамы). Все файлы соблюдают контракт с `--strict`.

## Пересобрать

```bash
python3 sources/generate/make_zombie_cats_pack.py   # каждый ассет через gen, затем диорама
python3 meshgate.py samples                         # пересоберёт пак вместе с остальными примерами
```

## Как использовать

- **Веб:** `python3 meshgate.py serve` → в галерее есть группа «Zombie Cats pack».
- **Unity:** `MeshGateSampleTools.BuildAll` копирует пак и собирает `Assets/MeshGate/ZombieCatsDemo.unity`; `MeshGateAsset` с `playOnLoad = "shamble"` заставляет кота идти в рантайме.
- **Godot:** `targets/godot/sync_samples.sh`, затем открой `demo_pack.tscn` (диорама с `play_on_load = "shamble"` и забор с коллизией).
- **Unreal:** `meshgate_import.import_pack("/path/samples/packs/zombie_cats")` — `.unreal.fbx` с UCX для статичных пропсов, иначе GLB, кот — как Skeletal Mesh.

![Коты-зомби в Godot 4 с проигрываемым клипом shamble](../../../docs/img/pack-zombie-cats-godot.png)
