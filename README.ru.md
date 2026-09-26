[English](README.md) · **Русский**

# MeshGate

> Шлюз ассетов: один экспорт из **Blender / Maya** → веб и игровые движки **Unity, Godot, Unreal**.

Документация доступна на английском и русском — на каждой странице вверху есть переключатель языка.

**Начни здесь → [С чего начать](docs/getting-started.ru.md):** что поставить, как подключить нейросеть и что важно
знать для web, Unity, Godot и Unreal.

MeshGate — тулкит, который приводит 3D-ассет из DCC-редактора к единому нормализованному **glTF/GLB** по строгому «контракту ассета», а затем доставляет его в любой рантайм: браузер (Three.js) и движки. Архитектура «ступица и спицы»: в центре — канонический GLB, вокруг — сменные адаптеры источников и целей. Добавить новый редактор или движок = добавить адаптер, не трогая ядро.

Это самостоятельный инструмент (весь код наш; проприетарная лицензия, см. [Лицензия](#лицензия)). Идея пайплайна (DCC → glTF → рантайм) — отраслевой стандарт; реализация оригинальная.

## Зачем

- Один ассет — везде: сделал в Blender или Maya, получил рабочую загрузку в вебе и в трёх движках.
- Предсказуемость: «контракт ассета» (масштаб, оси, материалы, имена) убирает «у меня повёрнуто/огромное/чёрное».
- Проверяемость: валидатор ловит проблемы до того, как ассет попал в движок.

## Формат-обменник

Ядро — **glTF 2.0 (.glb)**: общий знаменатель для веба и реалтайма (Blender родной, Godot/Unreal родной импорт, Unity через glTFast, Web через Three.js). Для тяжёлых риг/сцен и Maya-происхождения предусмотрен запасной путь через FBX/USD (см. `docs/architecture.md`).

## В Blender: аддон (без терминала)

Установи одной командой — `python3 meshgate.py install-blender` (сначала закрой Blender) — или вручную из `meshgate-blender-<версия>.zip`: Blender 4.2+ — перетащи zip в окно; Blender 3.5–4.1 — Preferences → Add-ons → Install. Дальше **N → MeshGate**: отметь цели, нажми **Проверить**, **Исправить всё**, **Экспорт**. Получишь проверенный GLB плюс FBX, коллизии `UCX_` для Unreal, `-convcolonly` для Godot и меши `_LOD` для Unity, результат откроется в браузере. Проверено на Blender 3.5, 4.2 LTS и 5.2 LTS — см. [sources/blender/README.ru.md](sources/blender/README.ru.md).

## Пример пака: Коты-зомби в трёх стилях

Одни и те же одиннадцать ассетов, сгенерированные MeshGate в трёх стилях. Одно описание на ассет и рендер собранного
вручную оригинала ушли ИИ по разу на стиль; дальше движок kit закрепляет вид: **low-poly** — гранёный и в разы легче,
**realistic** — с грязью, разбросом цвета и рельефом, запечёнными в текстуры. Каждый файл укладывается в бюджет каждого
уровня. Пересобрать без ИИ — `python3 sources/generate/make_style_packs.py`
([как это работает](docs/generation.ru.md#стили-которые-выглядят-по-разному)).

![Коты-зомби: stylized, low-poly и realistic](docs/img/zc-styles-lineup.jpg)

| Stylized | Low-poly | Realistic |
|---|---|---|
| ![Диорама stylized](docs/img/zc-diorama-stylized.jpg) | ![Диорама low-poly](docs/img/zc-diorama-lowpoly.jpg) | ![Диорама realistic](docs/img/zc-diorama-realistic.jpg) |

Исходный пак, собранный вручную: [`samples/packs/zombie_cats`](samples/packs/zombie_cats/README.ru.md) — 11 стилизованных ассетов и диорама (заборы со штакетником-ушками, фонари-рыбы, токсичная банка корма, риггованный кот-зомби на Humanoid), построенные одним скриптом Blender с одним материалом-палитрой, вариантами с коллизиями для Unreal и Godot и проверенные в веб-вьюере, Unity, Godot и по API Unreal.

![Коты-зомби в Unity](docs/img/pack-zombie-cats-unity.png)

## Быстрый старт (сквозняк Blender → Web)

```bash
# 0. Ничего не экспортируя — посмотреть готовый пример:
python3 targets/web/serve.py            # http://localhost:8770/targets/web/ → samples/meshgate_demo.glb

# 1. Экспорт своего ассета из Blender по контракту (headless) + проверка сразу:
blender -b твой.blend -P sources/blender/export_meshgate.py -- --out samples/asset.glb --validate
#    флаги: --draco (сжатие геометрии), --fbx (плюс FBX для редактора Unity/Unreal), --no-animations, --selection, --image-format WEBP

# 2. Отдельная проверка по контракту (stdlib, годится для CI):
python3 core/validate_glb.py samples/asset.glb            # --strict: предупреждения = ошибки, --json: для машин

# 3. Просмотр:
python3 targets/web/serve.py --glb samples/asset.glb
```

Примеры в `samples/` — «сундук с маяком», фонарь (стекло, эмиссия), бочка (normal-карта), дрон (иерархия, роторы) и риггованный персонаж `meshgate_hero` (скелет Unity Humanoid, UV, анимации на костях); свой персонаж — `sources/blender/animate_humanoid.py`. Сундук: иерархия, крышка на петле, две анимации, PBR-текстуры, эмиссия, стекло, Draco-вариант. Он же — тест для всех адаптеров целей. Веб-вьюер: наведение/клик/фокус по объектам, дерево, анимации с таймлайном, HDRI, тени, Draco/KTX2/meshopt, drag-and-drop своих файлов — см. [targets/web/README.md](targets/web/README.ru.md).

## Генерация по описанию или картинке

- **Текст → 3D:** `python3 meshgate.py gen "деревянная мельница с вращающимися лопастями"` просит твой ИИ-инструмент
  командной строки (Claude Code, Codex, Gemini, Ollama или любой другой) написать короткую функцию `build(mg)` на
  наборе для моделирования MeshGate. Потом строит модель отдельно под каждый уровень качества и возвращает проблемы
  ИИ, пока сборка не станет чистой.
- **Картинка → 3D:** `python3 meshgate.py gen --image photo.jpg` запускает нейросеть. Это TripoSR на твоей машине (MIT,
  ставится одной командой) или Meshy, Tripo, TRELLIS, Hunyuan3D в облаке. Потом MeshGate выпрямляет сетку, упрощает её
  под каждый уровень, строит развёртку и запекает цвет и нормали.
- **Любая сетка:** `--mesh file.glb` так же доводит до контракта скачанную модель.

![Картинки через оба движка](docs/img/picture-to-3d.png)

Подробности — [docs/generation.ru.md](docs/generation.ru.md).

## MeshGate Studio: десктоп-приложение

[MeshGate Studio](apps/studio/README.ru.md) — генерация в окне для macOS и Windows: описание, стиль, уровни, потом
3D-просмотр каждого уровня, ход каждой попытки и библиотека всего сделанного. Запускается без установки командой
`python3 meshgate.py studio` или собирается как приложение на Tauri (около 6 МБ).

![MeshGate Studio](docs/img/studio.png)

## Уровни качества: мобильные слабые / средние / мощные и PC

Бюджеты и настройки рендера для четырёх уровней устройств лежат в [`core/profiles.json`](core/profiles.json): валидатор проверяет по ним файлы (`--profile all`), аддон Blender экспортирует `<name>.<уровень>.glb` в пределах бюджета, а веб-вьюер, Unity, Godot и Unreal берут файлы и рендер своего уровня (на PC — мягкие тени, AO, bloom). Подробно — [docs/quality-tiers.ru.md](docs/quality-tiers.ru.md).

## Одна команда: `meshgate.py`

```bash
python3 meshgate.py doctor                                   # какие инструменты найдены (Blender, Unity, Godot)
python3 meshgate.py export scene.blend --out build/asset.glb --fbx   # экспорт по контракту + проверка
python3 meshgate.py character avatar.glb --out build/hero.glb        # риггованный гуманоид → контракт (+ idle/wave)
python3 meshgate.py validate build/asset.glb build/asset.fbx --strict
python3 meshgate.py serve --glb build/asset.glb              # веб-вьюер
python3 meshgate.py samples                                  # пересобрать все демо-ассеты из их Blender-скриптов
python3 meshgate.py check all                                # проверки web + Unity + Godot, headless
python3 meshgate.py gen "чугунный пожарный гидрант" --size 0.8   # текст → ассет по уровням качества через ИИ-CLI
python3 meshgate.py studio                                   # MeshGate Studio в браузере
```

Пути к инструментам находятся сами; переопределить — `MESHGATE_BLENDER`, `MESHGATE_UNITY`, `MESHGATE_GODOT`.

## Навык для агента

[`SKILL.ru.md`](SKILL.ru.md) превращает пайплайн в повторяемый навык для ИИ-агента (Claude Code, Codex): классифицировать вход → подготовить в Blender → экспортировать → каждое предупреждение валидатора превратить в правку → доставить в web/Unity/Godot/Unreal → проверить headless → отчитаться. Установка: `python3 scripts/install_skill.py` (`--codex` для Codex).

## Целевые движки

| Цель | Как | Статус |
|---|---|---|
| Web | `targets/web` — библиотека `meshgate-viewer.js` + демо-страница на Three.js | готово (v0.2) |
| Unity 6 | `targets/unity` — UPM-пакет `com.meshgate.unity` поверх Unity glTFast, sample-проект, PlayMode-тесты; FBX как запасной путь для редактора | готово (v0.3) |
| Godot 4 | `targets/godot` — аддон `meshgate` (рантайм-загрузка, анимации, коллизии, интерактив, орбита), демо-проект, headless-проверка | готово (v0.4) |
| Unreal 5 | `targets/unreal` — content-only плагин: импорт через Interchange/старый FBX с пайплайном MeshGate, UCX-коллизии, демо-уровень, Humanoid→Mannequin, рецепт glTFRuntime | сверено с Python API UE 5.4/5.5/5.6; живого прогона ещё не было |

## Структура

```
meshgate.py     CLI: doctor, export, character, validate, serve, samples, check, gen, studio
SKILL.md        навык для агента (+ SKILL.ru.md), установка — scripts/install_skill.py
core/           контракт ассета + валидаторы GLB и FBX (наш код, stdlib)
sources/blender аддон Blender (проверка · исправление · экспорт, 3.5–5.x), набор для моделирования, headless-экспорт, генераторы демо
sources/generate текст/картинка → ассет: промпт, адаптеры ИИ-CLI, ограждения, генераторы сеток, доводка, примеры
apps/studio     MeshGate Studio: локальный сервер + интерфейс, оболочка Tauri для macOS и Windows
sources/maya    пути из Maya (FBX→glTF / USD / плагин)
samples/        демо-ассет: .blend, .glb, .draco.glb
targets/web     библиотека-вьюер meshgate-viewer.js + демо-страница (Three.js, MIT)
targets/unity   UPM-пакет поверх Unity glTFast + sample-проект с PlayMode-тестами
targets/godot   аддон meshgate + демо-проект + headless-проверка
targets/unreal  плагин MeshGate (Python-скрипты редактора) + рецепты
docs/           контракт ассета, архитектура, видение, роадмап
.github/        CI: валидация примеров по контракту (--strict)
```

## Статус

v0.6.2. Генерация работает по описанию (код набора от любого ИИ-CLI) и по картинке (TripoSR локально или Meshy,
Tripo, TRELLIS, Hunyuan3D), с проверенным файлом на каждый уровень качества; MeshGate Studio оборачивает её в
приложение для macOS и Windows. Аддон Blender готов для всех
(проверено на Blender 3.5, 4.2 LTS и 5.2 LTS). У Web, Unity и Godot общий API и автоматические проверки контракта;
Unreal сверен с его Python API без установки движка. Сгенерированные ассеты проходят те же проверки движков, что и
собранные вручную примеры. Дальше — живой прогон Unreal, Maya, публичные релизы; персонажи и перенос PBR-карт позже. Роадмап — `docs/roadmap.ru.md`.

## Лицензия

Проприетарная, все права защищены, см. [LICENSE](LICENSE) (текст на английском). Можно пользоваться официальными
релизами и выпускать игры с плагинами; созданные ассеты принадлежат тебе. Копировать, распространять или менять код —
только с письменного разрешения. Сторонние компоненты сохраняют свои лицензии: [THIRD_PARTY_NOTICES.ru.md](THIRD_PARTY_NOTICES.ru.md).
Версии, полученные раньше под MIT, остаются под MIT.
