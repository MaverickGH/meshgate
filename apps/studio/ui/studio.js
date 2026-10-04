// MeshGate Studio UI — talks to apps/studio/server.py (same origin), shows results in the MeshGate web viewer.

const token = new URLSearchParams(location.search).get("t") || "";
const $ = (id) => document.getElementById(id);
const api = async (path, body) => {
  const res = await fetch(path, body === undefined
    ? { headers: { "X-MeshGate-Token": token }, cache: "no-store" }
    : { method: "POST", headers: { "X-MeshGate-Token": token, "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
};
const fileUrl = (name, file) => `/files/${encodeURIComponent(name)}/${encodeURIComponent(file)}?t=${encodeURIComponent(token)}`;

// ---------------------------------------------------------------- i18n
const STRINGS = {
  en: {
    examples_label: "Prompt examples", output_settings: "Output settings", create_asset: "Create asset", create_intro: "Describe your idea and configure the game-ready build.", scene_preview: "Preview", activity: "Build activity",
    studio: "Studio", connect_intro: "Text → 3D needs one AI command-line tool. Picture → 3D needs TripoSR (local) or a cloud key. You do this once.",
    connect_cli: "AI command line — writes the model's code", connect_mesh: "Picture → 3D", connect_keys: "API keys", describe: "Describe the model", describe_ph: "A wooden windmill with turning blades", style: "Style",
    name: "Name", size: "Size, m", auto: "auto", tiers: "Quality tiers",
    tiers_hint: "The same model is built once per tier, with as much detail as the tier affords.", engines: "Engines",
    ai_settings: "AI and advanced", ai: "AI command line", model: "Model", model_ph: "default of the CLI",
    tune: "Refine", tune_words: "Change in words", tune_words_ph: "Bigger ears, longer fur on the chest, eyes a little lower…",
    tune_words_go: "Change with AI", tune_params: "Parameters", tune_rebuild: "Rebuild", tune_reset: "Defaults",
    tune_versions: "Versions", tune_restore: "Restore", tune_no_versions: "no earlier versions yet", tune_first: "as built",
    tune_no_params: "This model has no sliders yet — ask the AI in words to add some (mg.param).",
    tune_mesh_hint: "Models from a mesh generator are refined by generating again; tuning works on kit models.",
    clip_hint: "Play this clip; click again to stop",
    meter_start: "Starting…", meter_left: "left", meter_soon: "almost there", meter_done: "done", min: "min",
    review_word: "review", attempt_word: "attempt",
    meter_steps: { building: "building", ask: "asking the AI", compare: "the AI compares", render: "rendering views",
                   concept: "drawing the concept", mesh: "generating the 3D model", master: "baking the 8K master" },
    ai_cmd: "Custom command", attempts: "Attempts", review: "AI review rounds",
    review_hint: "After a clean build the AI sees its model from four sides next to the picture and improves the code", collision: "Collision", none: "none", generate: "Generate",
    generating: "Generating…", cancel: "Cancel", wireframe: "Wireframe", reveal: "Show files", progress: "Progress",
    code: "Code", library: "Library", empty: "Describe a model and press Generate. Results appear here, one file per quality tier.",
    not_installed: "not installed", no_blender: "Blender not found", blender: "Blender", nothing: "Nothing generated yet.",
    styles: { stylized: "Stylized", lowpoly: "Low-poly", realistic: "Realistic", toon: "Toon" },
    tris: "tris", of: "of", clips: "clips", attempts_forms: ["attempt", "attempts"], seconds: "s", over: "over budget",
    need_login: "Sign-in needed", attempt: "Attempt", own_code: "own build code",
    picture: "Picture or model", drop: "Drop a picture or click — optional. With a picture you get image → 3D; with a model of your own (GLB, FBX, OBJ, PLY, STL) it goes to the library, cleaned and baked per tier.",
    model_picked: "your model — Generate puts it in the library", uploading_model: "Uploading the model…",
    dock_texture: "Texture", dock_remesh: "Remesh", dock_uv: "Unwrap UV", dock_mesh_title: "Remesh and UV", dock_download: "Download",
    dock_target: "Target polycount", dock_default: "Default",
    dock_target_hint: "The triangle count of the model. Every tier gets it, or less when its own budget is lower; Default keeps the tier budgets.",
    dock_topo_hint: "Quads: a neural or your own mesh is remeshed into clean quads, and FBX and .blend keep them. Triangles are what engines draw — GLB is always triangles.",
    dock_uv_hint: "Every build unwraps the model itself: seams on hard edges, islands packed without overlaps, then textures baked into them. Kit models keep their colours in palette cells.",
    dock_uv_show: "Show the UV grid on the model", dock_uv_hide: "Hide the UV grid", dock_uv_go: "Unwrap and bake again",
    dock_tex_hint: "The largest texture of the PC file; the phone tiers keep their own limits. 8K also writes a master file.",
    dock_pbr: "Full PBR maps", dock_apply: "Apply and rebuild", dock_now: "Now: {tris} triangles on {tier}.",
    dock_no_source: "This model has no source to rebuild from.",
    dock_quad_warn: "Below about 8K triangles thin or open pieces (flaps, open boxes, leaves) cannot keep clean quads: they stay as triangles paired into quads, so the quad share drops. Each separate piece is remeshed on its own, so nothing tears.",
    send_to: "Send to…", send_project: "Project folder", send_go: "Send",
    send_title: "Send to {tool}", send_done: "{files} → {folder}", send_opened: "Opened {file} in Blender",
    send_where: { unity: "The GLB of every tier (glTFast) and the FBX go to Assets/MeshGate/<model>/. Send again after a change and Unity re-imports them.",
      godot: "The GLB of every tier goes to res://meshgate/<model>/; Godot imports it when it gets focus. Send again after a change to update it.",
      unreal: "The FBX goes to Content/MeshGate/<model>/; the editor offers to import new files. Send again after a change to re-import." },
    part_copy: "Duplicate", part_undo: "Undo",
    parts_keys: "W move · E turn · R scale · ⌘/Ctrl+D duplicate · Delete remove · ⌘/Ctrl+Z undo",
    paint: { red: "Red", orange: "Orange", yellow: "Yellow", green: "Green", teal: "Teal", blue: "Blue", purple: "Purple", pink: "Pink",
      brown: "Brown", tan: "Tan", white: "White", grey: "Grey", black: "Black" },
    look: "Appearance", look_shape: "Shape", look_colours: "Colours", look_random: "Random", look_reset: "As built",
    look_save: "Save the look",
    look_hint: "Sliders from the model's morph targets: they change it at once, as a game's character creator does, and stay in the GLB and FBX for your game to move. Save rebuilds every tier with this look.",
    look_none: "This model has no sliders. Kit code declares them with mg.morph — ask for a character creator in words on the Refine tab.",
    look_missing: "not on this tier (its file budget)", look_baked: "Colours of a baked texture change when you save.",
    base_title: "Blender base", base_hint: "Load the chosen model into MeshGate live. After your edits, save a new version of the base.",
    base_load: "Load into the live scene", base_save: "Save a new version of the base", base_undo: "Undo the Blender edit",
    base_compare: "Compare with the reference", base_full: "Open the comparison large", base_source: "Built from: ",
    base_saved: "Base saved — the next build uses it", base_report: "The last saved comparison report",
    base_loaded: "Model loaded into MeshGate live", base_undone: "Edit undone",
    parts: "Parts", parts_title: "Parts of the model", parts_split: "Split this model into parts",
    parts_hint: "Click a part in the view or the list, then drag the handles, repaint, duplicate or remove it. Save rebuilds every tier with your changes; they stay with the model and come back on every rebuild.",
    parts_none: "This model is one piece. Split it to move, turn, scale, repaint or remove its parts one by one.",
    parts_cannot: "This model has no source to rebuild from.", part_move: "Move", part_turn: "Turn", part_scale: "Scale",
    part_colour: "Colour", part_as_built: "as built", part_delete: "Remove", part_restore: "Keep", part_reset: "Undo its changes",
    parts_save: "Save and rebuild", parts_clear: "Back to as built", part_colour_mesh: "A copy of a baked part keeps its look (it shares the texture); repaint the part itself",
    split: "Split into parts — every separate thing its own object",
    split_hint: "A pile of crates becomes one object per crate, each named by its colour with its origin at its base, so it can be moved, swapped or reworked on its own in Unity, Godot, Unreal or Blender.", remove: "Remove",
    engine: "How to build", engine_opts: { auto: "Auto", kit: "Kit code", mesh: "Neural mesh" },
    engine_hints: { auto: "Neural mesh when there is a picture and a generator is ready, otherwise kit code.",
      kit: "An AI writes clean, editable build code: hard-surface and stylized props. Works with a picture as a guide.",
      mesh: "A neural generator makes the mesh (TripoSR, Meshy, Tripo, TRELLIS); MeshGate bakes it per tier." },
    provider: "Mesh generator", auto_pick: "first ready", detail: "Detail ×", turn: "Turn, °", not_ready: "not ready",
    concept: "Draw a concept picture first (Codex, OpenAI or fal), then build from it",
    concept_none: "no picture generator — install Codex (ChatGPT sign-in) or add an OpenAI / fal key",
    texture_size: "Texture size", topology: "Topology", topo_tri: "Triangles", topo_quad: "Quads",
    pose: "Character pose", pose_none: "None (as modelled)",
    outline: "Ink outline", outline_auto: "Auto (toon style)", on: "On", off: "Off",
    outline_hint: "A dark line round the silhouette, drawn the way games draw it (an inverted hull) on mobile-high and PC.",
    pose_hint: "The rest pose of a rigged character in the file. A or T is the bind pose that retargeting and Humanoid setups expect; the clips still play as designed.",
    pbr: "Full PBR maps for every style (colour, occlusion, roughness, metallic, normal)",
    quality_hint: "Textures are baked for the realistic style and with full PBR; the phone tiers keep their own limits, 8K also writes a master file. Quads go into FBX and .blend — GLB is always triangles.",
    anim: "Animations", anim_ph: "open: the lid opens and closes\nidle: the lantern sways",
    anim_hint: "One clip per line, name: what happens. The code engine gives moving parts their own clips.",
    pictures: "Pictures from text", colors: "Colours", colors_opts: { texture: "Textures", vertex: "Vertex colours" },
    tris_hint: "One slider for the triangle count. The ticks are the tier budgets: crossing one changes the tier. Every tier up to it is built; the top one gets your number as its limit.", tiers_built: "Built",
    need_input: "Describe the model or add a picture.", uploading: "Uploading the picture…", engine_label: "engine",
    setup_triposr: "Install TripoSR — local, free, ~3 GB",
    connect: "Status & AI", connect_title: "Status & connections", connect_tools: "Blender and game engines", refresh: "Refresh",
    connect_components: "Optional components — installed separately",
    components_intro: "Big local models, each in its own folder under ~/.cache/meshgate. Install them when you need them.",
    installed: "installed", comp_missing: "installed, one step left", then: "then:", about: "About",
    install_addon: "Install add-on", plugin_files: "Plugin files", not_found: "not found", addon_ok: "add-on installed", addon_missing: "add-on not installed", install: "Install", sign_in: "Sign in", download: "Download",
    ready: "ready", not_signed_in: "not signed in", missing: "not installed", save: "Save", clear: "Clear",
    key_saved: "saved", key_placeholder: "paste the key", terminal_opened: "A terminal window opened — finish there, this updates by itself.",
    no_npm: "needs Node.js (npm) — https://nodejs.org", keys_where: "Keys are stored on this computer only, in", cancelled: "Cancelled — Blender and the generator were stopped.", examples: ["Wooden windmill with turning blades", "Sci-fi supply crate with glowing strips",
      "Old cast-iron street lamp", "Cute cactus in a clay pot", "Medieval wooden cart"],
  },
  ru: {
    examples_label: "Примеры описаний", output_settings: "Параметры экспорта", create_asset: "Создание ассета", create_intro: "Опиши идею и настрой сборку для игрового движка.", scene_preview: "Просмотр", activity: "Ход сборки",
    studio: "Студия", connect_intro: "Для текста → 3D нужен один ИИ-инструмент командной строки. Для картинки → 3D — TripoSR (локально) или облачный ключ. Это делается один раз.",
    connect_cli: "ИИ в командной строке — пишет код модели", connect_mesh: "Картинка → 3D", connect_keys: "Ключи API", describe: "Опиши модель", describe_ph: "Деревянная мельница с вращающимися лопастями", style: "Стиль",
    name: "Имя", size: "Размер, м", auto: "авто", tiers: "Уровни качества",
    tiers_hint: "Одна и та же модель строится под каждый уровень — с той детализацией, которую он позволяет.", engines: "Движки",
    ai_settings: "Нейросеть и дополнительно", ai: "ИИ в командной строке", model: "Модель", model_ph: "по умолчанию CLI",
    tune: "Доработка", tune_words: "Изменить словами", tune_words_ph: "Уши побольше, шерсть на груди длиннее, глаза чуть ниже…",
    tune_words_go: "Изменить с ИИ", tune_params: "Параметры", tune_rebuild: "Пересобрать", tune_reset: "По умолчанию",
    tune_versions: "Версии", tune_restore: "Вернуть", tune_no_versions: "пока нет прошлых версий", tune_first: "как собрано",
    tune_no_params: "У этой модели пока нет ползунков — попроси ИИ словами добавить их (mg.param).",
    tune_mesh_hint: "Модели из нейросети дорабатываются новой генерацией; доработка работает для моделей kit.",
    clip_hint: "Проиграть клип; ещё раз — остановить",
    meter_start: "Запуск…", meter_left: "осталось", meter_soon: "почти готово", meter_done: "готово", min: "мин",
    review_word: "ревью", attempt_word: "попытка",
    meter_steps: { building: "сборка", ask: "ИИ пишет код", compare: "ИИ сравнивает", render: "рендер видов",
                   concept: "рисуем концепт", mesh: "нейросеть делает 3D", master: "запекаем мастер 8K" },
    ai_cmd: "Своя команда", attempts: "Попытки", review: "Круги ревью ИИ",
    review_hint: "После чистой сборки ИИ видит свою модель с четырёх сторон рядом с картинкой и улучшает код", collision: "Коллизия", none: "нет", generate: "Сгенерировать",
    generating: "Генерирую…", cancel: "Отмена", wireframe: "Сетка", reveal: "Показать файлы", progress: "Ход работы",
    code: "Код", library: "Библиотека", empty: "Опиши модель и нажми «Сгенерировать». Результат появится здесь — по файлу на каждый уровень качества.",
    not_installed: "не установлен", no_blender: "Blender не найден", blender: "Blender", nothing: "Пока ничего не сгенерировано.",
    styles: { stylized: "Стилизация", lowpoly: "Low-poly", realistic: "Реализм", toon: "Мульт" },
    tris: "трис", of: "из", clips: "клипы", attempts_forms: ["попытка", "попытки", "попыток"], seconds: "с", over: "сверх бюджета",
    need_login: "Нужен вход", attempt: "Попытка", own_code: "свой код сборки",
    picture: "Картинка или модель", drop: "Перетащи картинку или нажми — по желанию. С картинкой получится картинка → 3D, а своя модель (GLB, FBX, OBJ, PLY, STL) ляжет в библиотеку: её почистят и запекут под каждый уровень.",
    model_picked: "твоя модель — «Создать» положит её в библиотеку", uploading_model: "Загружаю модель…",
    dock_texture: "Текстура", dock_remesh: "Ремеш", dock_uv: "Развернуть UV", dock_mesh_title: "Ремеш и UV", dock_download: "Скачать",
    dock_target: "Целевой полигонаж", dock_default: "Обычный",
    dock_target_hint: "Число треугольников модели. Его получит каждый уровень, или меньше, если у уровня свой бюджет ниже; «Обычный» оставляет бюджеты уровней.",
    dock_topo_hint: "Четырёхугольники: сетка из нейросети или твоя модель перестраивается в чистые квады, FBX и .blend их сохраняют. Треугольники рисуют движки — GLB всегда из треугольников.",
    dock_uv_hint: "Каждая сборка сама разворачивает модель: швы по жёстким рёбрам, острова уложены без наложений, в них запекаются текстуры. У моделей kit цвета лежат в ячейках палитры.",
    dock_uv_show: "Показать UV-сетку на модели", dock_uv_hide: "Скрыть UV-сетку", dock_uv_go: "Развернуть и запечь заново",
    dock_tex_hint: "Самая большая текстура файла PC; уровни для телефонов держат свои лимиты. 8K ещё пишет мастер-файл.",
    dock_pbr: "Полный набор PBR", dock_apply: "Применить и пересобрать", dock_now: "Сейчас: {tris} треугольников на {tier}.",
    dock_no_source: "У этой модели нет исходника для пересборки.",
    dock_quad_warn: "Меньше ~8K треугольников тонкие и открытые куски (клапаны, открытые коробки, листья) не удержат чистые квады: они останутся треугольниками, спаренными в квады, и доля квадов упадёт. Каждый отдельный кусок перестраивается сам по себе, так что ничего не рвётся.",
    send_to: "Отправить в…", send_project: "Папка проекта", send_go: "Отправить",
    send_title: "Отправить в {tool}", send_done: "{files} → {folder}", send_opened: "{file} открыт в Blender",
    send_where: { unity: "GLB каждого уровня (glTFast) и FBX лягут в Assets/MeshGate/<модель>/. Отправь снова после правки — Unity переимпортирует их.",
      godot: "GLB каждого уровня ляжет в res://meshgate/<модель>/; Godot импортирует его, когда окно получит фокус. Отправь снова после правки, чтобы обновить.",
      unreal: "FBX ляжет в Content/MeshGate/<модель>/; редактор предложит импортировать новые файлы. Отправь снова после правки — он переимпортирует." },
    part_copy: "Дублировать", part_undo: "Отменить",
    parts_keys: "W двигать · E повернуть · R масштаб · ⌘/Ctrl+D дублировать · Delete удалить · ⌘/Ctrl+Z отменить",
    paint: { red: "Красный", orange: "Оранжевый", yellow: "Жёлтый", green: "Зелёный", teal: "Бирюзовый", blue: "Синий", purple: "Фиолетовый",
      pink: "Розовый", brown: "Коричневый", tan: "Светло-коричневый", white: "Белый", grey: "Серый", black: "Чёрный" },
    look: "Внешность", look_shape: "Форма", look_colours: "Цвета", look_random: "Случайно", look_reset: "Как было",
    look_save: "Сохранить внешность",
    look_hint: "Ползунки из морфов модели: меняют её сразу, как редактор персонажа в игре, и остаются в GLB и FBX — их может двигать и твоя игра. «Сохранить» пересоберёт все уровни с этой внешностью.",
    look_none: "У этой модели нет ползунков. Код kit объявляет их через mg.morph — попроси редактор персонажа словами на вкладке «Доработка».",
    look_missing: "нет на этом уровне (бюджет файла)", look_baked: "Цвета запечённой текстуры поменяются при сохранении.",
    base_title: "База Blender", base_hint: "Загрузите выбранную модель в MeshGate live. После правок сохраните отдельную версию базы.",
    base_load: "Загрузить в live-сцену", base_save: "Сохранить новую версию базы", base_undo: "Отменить правку Blender",
    base_compare: "Сравнить с референсом", base_full: "Открыть сравнение крупно", base_source: "Источник сборки: ",
    base_saved: "База сохранена и будет использована при следующей сборке", base_report: "Последний сохранённый отчёт сравнения",
    base_loaded: "Модель загружена в MeshGate live", base_undone: "Правка отменена",
    parts: "Части", parts_title: "Части модели", parts_split: "Разделить эту модель на части",
    parts_hint: "Нажми на часть в окне или в списке и тяни за ручки, перекрашивай, дублируй или удаляй. «Сохранить» пересоберёт все уровни с твоими правками; они остаются с моделью и повторяются при каждой пересборке.",
    parts_none: "Эта модель — один кусок. Раздели её, чтобы двигать, поворачивать, масштабировать, перекрашивать или удалять части по отдельности.",
    parts_cannot: "У этой модели нет исходника для пересборки.", part_move: "Двигать", part_turn: "Повернуть", part_scale: "Масштаб",
    part_colour: "Цвет", part_as_built: "как было", part_delete: "Удалить", part_restore: "Оставить", part_reset: "Отменить её правки",
    parts_save: "Сохранить и пересобрать", parts_clear: "Вернуть как было", part_colour_mesh: "Копия запечённой части выглядит как она (у них общая текстура); перекрась саму часть",
    split: "Разделить на части — каждая отдельная вещь своим объектом",
    split_hint: "Куча ящиков станет отдельным объектом на каждый ящик: имя по цвету, точка опоры внизу — их можно двигать, менять и переделывать по отдельности в Unity, Godot, Unreal или Blender.", remove: "Убрать",
    engine: "Как строить", engine_opts: { auto: "Авто", kit: "Код набора", mesh: "Нейросетка" },
    engine_hints: { auto: "Нейросетка, если есть картинка и готов генератор, иначе код набора.",
      kit: "ИИ пишет чистый редактируемый код модели: предметы и стилизация. Картинку использует как образец.",
      mesh: "Нейросеть делает сетку (TripoSR, Meshy, Tripo, TRELLIS), MeshGate запекает её под каждый уровень." },
    provider: "Генератор сетки", auto_pick: "первый готовый", detail: "Детализация ×", turn: "Поворот, °", not_ready: "не готов",
    concept: "Сначала нарисовать концепт (Codex, OpenAI или fal) и строить по нему",
    concept_none: "нет генератора картинок — поставь Codex (вход через ChatGPT) или добавь ключ OpenAI / fal",
    texture_size: "Размер текстур", topology: "Топология", topo_tri: "Треугольники", topo_quad: "Квады",
    pose: "Поза персонажа", pose_none: "Нет (как смоделирован)",
    outline: "Обводка", outline_auto: "Авто (стиль «мульт»)", on: "Вкл", off: "Выкл",
    outline_hint: "Тёмная линия по силуэту, как её рисуют в играх (вывернутая оболочка), на уровнях mobile-high и PC.",
    pose_hint: "Поза покоя персонажа со скелетом в файле. A или T — та bind-поза, которую ждут ретаргетинг и Humanoid; клипы играются как задуманы.",
    pbr: "Полный набор PBR-карт для любого стиля (цвет, затенение, шероховатость, металличность, нормали)",
    quality_hint: "Текстуры запекаются в стиле «реализм» и с полным PBR; уровни для телефонов держат свои лимиты, 8K ещё пишет мастер-файл. Квады идут в FBX и .blend — GLB всегда из треугольников.",
    anim: "Анимации", anim_ph: "open: крышка открывается и закрывается\nidle: фонарь покачивается",
    anim_hint: "По клипу в строке, имя: что происходит. Движок кода делает подвижные части отдельными клипами.",
    pictures: "Картинки по тексту", colors: "Цвета", colors_opts: { texture: "Текстуры", vertex: "В вершинах" },
    tris_hint: "Один ползунок — число треугольников. Риски — бюджеты уровней: перешёл риску — сменился уровень. Строятся все уровни до него, верхний получает твоё число как лимит.", tiers_built: "Строим",
    need_input: "Опиши модель или добавь картинку.", uploading: "Загружаю картинку…", engine_label: "движок",
    setup_triposr: "Установить TripoSR — локально, бесплатно, ~3 ГБ",
    connect: "Статус и ИИ", connect_title: "Статус и подключения", connect_tools: "Blender и игровые движки", refresh: "Обновить",
    connect_components: "Дополнительные компоненты — ставятся отдельно",
    components_intro: "Большие локальные модели, каждая в своей папке в ~/.cache/meshgate. Ставь, когда понадобятся.",
    installed: "установлен", comp_missing: "установлен, остался один шаг", then: "потом:", about: "Подробнее",
    install_addon: "Поставить аддон", plugin_files: "Файлы плагина", not_found: "не найден", addon_ok: "аддон установлен", addon_missing: "аддон не установлен", install: "Установить", sign_in: "Войти", download: "Скачать",
    ready: "готов", not_signed_in: "нужен вход", missing: "не установлен", save: "Сохранить", clear: "Очистить",
    key_saved: "сохранён", key_placeholder: "вставь ключ", terminal_opened: "Открылось окно терминала — заверши там, здесь всё обновится само.",
    no_npm: "нужен Node.js (npm) — https://nodejs.org", keys_where: "Ключи хранятся только на этом компьютере, в файле", cancelled: "Отменено — Blender и генератор остановлены.", examples: ["Деревянная мельница с лопастями", "Научно-фантастический ящик со светящимися полосами",
      "Старый чугунный уличный фонарь", "Милый кактус в глиняном горшке", "Средневековая деревянная телега"],
  },
};
let lang = "";
try { lang = localStorage.getItem("mg-lang") || ""; } catch { /* private mode */ }
if (!lang) lang = (navigator.language || "en").toLowerCase().startsWith("ru") ? "ru" : "en";
const t = (k) => STRINGS[lang][k] ?? STRINGS.en[k] ?? k;
// plural forms: en [one, many], ru [одна, две–четыре, пять+]
const plural = (n, forms) => {
  if (forms.length === 2) return n === 1 ? forms[0] : forms[1];
  const m10 = n % 10, m100 = n % 100;
  return m10 === 1 && m100 !== 11 ? forms[0] : m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14) ? forms[1] : forms[2];
};

function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); el.setAttribute("aria-label", el.title); });
  $("lang").textContent = lang === "ru" ? "EN" : "RU";
  renderExamples(); renderStyles(); renderEngine(); renderColors(); if (status) { renderPills(); renderAi(); renderProviders(); }
  renderTierTabs(); renderLibrary();
}
$("lang").onclick = () => { lang = lang === "ru" ? "en" : "ru"; try { localStorage.setItem("mg-lang", lang); } catch { /* ignore */ } applyLang(); };

// ---------------------------------------------------------------- state
let status = null, library = [], current = null, currentTier = null, job = null, style = "stylized";
let engine = "auto", picture = null, model = null;   // picture / model = uploaded id
let colors = "texture";
let viewer = null, viewerFailed = false, wire = false;

function renderExamples() {
  $("examples").replaceChildren(...t("examples").map((ex) => {
    const b = document.createElement("button"); b.type = "button"; b.className = "chip"; b.textContent = ex;
    b.onclick = () => { $("description").value = ex; $("description").focus(); };
    return b;
  }));
}
function renderStyles() {
  const styles = t("styles");
  $("style").replaceChildren(...Object.keys(styles).map((id) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = styles[id];
    b.className = id === style ? "on" : ""; b.onclick = () => { style = id; renderStyles(); };
    return b;
  }));
}
function renderPills() {
  const pills = [];
  const blender = status.blender;
  pills.push(`<span class="pill ${blender ? "ok" : "bad"}">${blender ? t("blender") : t("no_blender")}</span>`);
  for (const [name, path] of Object.entries(status.ai)) {
    if (!path) continue;
    const out = status.signed_in?.[name] === false;
    pills.push(`<span class="pill ${out ? "bad" : "ok"}" title="${out ? status.login_hints?.[name] || "" : ""}">${name}${out ? " · " + t("need_login") : ""}</span>`);
  }
  for (const [id, p] of Object.entries(status.providers || {})) {
    if (p.ready && id !== "command") pills.push(`<span class="pill ok">${id}</span>`);
  }
  $("pills").innerHTML = pills.join("");
}
function renderAi() {
  const sel = $("ai"); const keep = sel.value;
  sel.replaceChildren(...Object.entries(status.ai).map(([name, path]) => {
    const o = document.createElement("option"); o.value = name;
    o.textContent = path ? name : `${name} — ${t("not_installed")}`; o.disabled = !path; return o;
  }));
  const firstInstalled = Object.entries(status.ai).find(([, p]) => p)?.[0];
  sel.value = keep && status.ai[keep] ? keep : firstInstalled || "claude";
  $("ai-hint").textContent = firstInstalled ? "" : `${t("ai")}: ${t("not_installed")} — ${Object.values(status.ai_urls).join(" · ")}`;
}
// One slider for the triangle count, on a log scale from 200 up to the PC budget. The tier the number falls in is
// named next to it and changes as the slider crosses a tier's budget (the ticks); every tier up to it is built, and
// that top tier gets the number as its own limit (at a tier's full budget: no limit).
const TRI_MIN = 200;
let triValue = null;   // null = the PC budget (everything, no own limit)
function tierScale() {
  const tiers = ["mobile-low", "mobile-mid", "mobile-high", "pc"].map((id) => status.tiers.find((x) => x.id === id)).filter(Boolean);
  const max = tiers[tiers.length - 1].max_tris;
  const pos = (n) => Math.log(n / TRI_MIN) / Math.log(max / TRI_MIN) * 1000;
  const val = (p) => { const n = TRI_MIN * (max / TRI_MIN) ** (p / 1000); const q = 10 ** Math.floor(Math.log10(n) - 1); return Math.min(max, Math.round(n / q) * q); };
  const tierOf = (n) => tiers.find((x) => n <= x.max_tris) || tiers[tiers.length - 1];
  return { tiers, max, pos, val, tierOf };
}
function tierPlan() {
  const { tiers, max, tierOf } = tierScale();
  const n = triValue ?? max, top = tierOf(n), upto = tiers.slice(0, tiers.indexOf(top) + 1);
  return { n, top, tiers: upto.map((x) => x.id), tris: n < top.max_tris ? { [top.id]: n } : {} };
}
function renderTiers() {
  const { tiers, max, pos, val } = tierScale();
  const box = $("tiers");
  box.className = "tri-slider";
  box.innerHTML = `<div class="tri-head"><span class="tri-tier"></span><input class="cap" type="number" min="${TRI_MIN}" max="${max}" step="100" title="${t("tris_hint")}"><span class="tri-unit">${t("tris")}</span></div>`
    + `<div class="tri-track"><input class="cap-range" type="range" min="0" max="1000" step="1" aria-label="${t("tiers")}">`
    + tiers.slice(0, -1).map((x) => `<span class="tick" style="left:${pos(x.max_tris) / 10}%" title="${x.label} ≤ ${x.max_tris.toLocaleString()}">`
      + `<i>${x.max_tris >= 1000 ? `${x.max_tris / 1000}k` : x.max_tris}</i></span>`).join("") + `</div>`
    + `<div class="tri-built"></div>`;
  const range = box.querySelector(".cap-range"), num = box.querySelector("input.cap");
  const show = () => {
    const plan = tierPlan();
    range.value = pos(plan.n); num.value = plan.n;
    range.style.setProperty("--fill", `${range.value / 10}%`);
    box.querySelector(".tri-tier").textContent = plan.top.label;
    box.querySelector(".tri-tier").title = plan.top.devices;
    box.querySelector(".tri-built").textContent = `${t("tiers_built")}: ${plan.tiers.map((id) => tiers.find((x) => x.id === id).label).join(" · ")}`
      + (Object.keys(plan.tris).length ? "" : ` — ${t("auto")}`);
  };
  range.oninput = () => { const v = val(+range.value); triValue = v >= max ? null : v; show(); };
  num.onchange = () => { const v = parseInt(num.value, 10); triValue = !Number.isFinite(v) || v >= max ? null : Math.max(TRI_MIN, v); show(); };
  show();
  $("targets").replaceChildren(...["web", "unity", "godot", "unreal"].map((id) => {
    const l = document.createElement("label"); l.className = "check";
    l.innerHTML = `<input type="checkbox" value="${id}" checked> ${id[0].toUpperCase() + id.slice(1)}`;
    return l;
  }));
}

function renderColors() {
  const names = t("colors_opts");
  $("colors").replaceChildren(...Object.keys(names).map((id) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = names[id];
    b.className = id === colors ? "on" : ""; b.onclick = () => { colors = id; renderColors(); };
    return b;
  }));
}
function renderEngine() {
  const names = t("engine_opts");
  $("engine").replaceChildren(...Object.keys(names).map((id) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = names[id];
    b.className = id === engine ? "on" : ""; b.onclick = () => { engine = id; renderEngine(); };
    return b;
  }));
  $("engine-hint").textContent = t("engine_hints")[engine];
}
function renderProviders() {
  const sel = $("provider"); const keep = sel.value;
  const auto = document.createElement("option"); auto.value = ""; auto.textContent = `${t("auto_pick")}`;
  sel.replaceChildren(auto, ...Object.entries(status.providers).filter(([id]) => id !== "command").map(([id, p]) => {
    const o = document.createElement("option"); o.value = id; o.disabled = !p.ready;
    o.textContent = p.ready ? p.label : `${p.label} — ${t("not_ready")}${p.key_env ? " (" + p.key_env + ")" : ""}`;
    return o;
  }));
  sel.value = keep && status.providers[keep]?.ready ? keep : "";
  $("fal_model").replaceChildren(...(status.fal_models || []).map((m) => { const o = document.createElement("option"); o.value = o.textContent = m; return o; }));
  const sync = () => $("fal-row").classList.toggle("hidden", sel.value !== "fal");
  sel.onchange = sync; sync();
  $("setup-triposr").classList.toggle("hidden", !!status.providers.triposr?.ready);
  const drawers = Object.entries(status.image_providers || {}).filter(([, ok]) => ok).map(([k]) => k);
  $("concept").disabled = !drawers.length;
  $("concept").parentElement.title = drawers.length ? drawers.join(", ") : t("concept_none");
}
async function runJob(start) {
  $("log").replaceChildren(); busy(true);
  try {
    job = await start();
    let since = 0;
    for (;;) {
      await new Promise((r) => setTimeout(r, 700));
      const s = await api(`/api/jobs/${job.id}?since=${since}`);
      s.lines.forEach(log); since = s.next;
      if (s.done) return s;
    }
  } finally { busy(false); }
}
$("setup-triposr").onclick = async () => {
  document.querySelector('[data-pane="log"]').click();
  try {
    await runJob(() => api("/api/setup", { provider: "triposr" }));
    status = await api("/api/status?refresh=1"); renderPills(); renderProviders();
  } catch (e) { log({ stage: "error", message: e.message }); } finally { job = null; }
};
async function pickModel(file) {
  const data = await new Promise((ok, fail) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = fail; r.readAsDataURL(file); });
  unpick(); $("drop-text").textContent = t("uploading_model");
  try {
    const up = await api("/api/upload-model", { data, filename: file.name });
    model = up.id;
    if (!$("name").value.trim()) $("name").value = up.name;
    $("unpick").classList.remove("hidden");
    $("drop-text").textContent = `${file.name} — ${t("model_picked")}`;
  } catch (e) { model = null; $("drop-text").textContent = e.message; }
}
async function pickPicture(file) {
  if (file && /\.(glb|fbx|obj|ply|stl)$/i.test(file.name)) return pickModel(file);
  if (!file || !/^image\/(png|jpeg|webp)$/.test(file.type)) return;
  model = null;
  const data = await new Promise((ok, fail) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = fail; r.readAsDataURL(file); });
  $("drop-text").textContent = t("uploading");
  try {
    picture = (await api("/api/upload", { data })).id;
    $("thumb").src = data; $("thumb").classList.remove("hidden"); $("unpick").classList.remove("hidden");
    $("drop-text").textContent = file.name;
  } catch (e) { picture = null; $("drop-text").textContent = e.message; }
}
function unpick(e) {
  e?.preventDefault(); e?.stopPropagation(); picture = null; model = null; $("file").value = "";
  $("thumb").classList.add("hidden"); $("unpick").classList.add("hidden"); $("drop-text").textContent = t("drop");
}
$("file").onchange = () => pickPicture($("file").files[0]);
$("unpick").onclick = unpick;
$("drop").addEventListener("dragover", (e) => { e.preventDefault(); $("drop").classList.add("over"); });
$("drop").addEventListener("dragleave", () => $("drop").classList.remove("over"));
$("drop").addEventListener("drop", (e) => { e.preventDefault(); $("drop").classList.remove("over"); pickPicture(e.dataTransfer.files[0]); });
$("drop").addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("file").click(); } });

// ---------------------------------------------------------------- connect AI
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
function btn(label, onClick, cls = "ghost small") { const b = el("button", cls, label); b.type = "button"; b.onclick = onClick; return b; }
let connectPoll = null;
async function openTerminal(ai, action) {
  try { await api("/api/terminal", { ai, action }); log({ stage: "start", message: t("terminal_opened") }); }
  catch (e) { log({ stage: "error", message: e.message }); }
  clearInterval(connectPoll);   // watch for the install / sign-in to finish
  let n = 0;
  connectPoll = setInterval(async () => {
    status = await api("/api/status?refresh=1").catch(() => status);
    renderConnect(); renderPills(); renderAi();
    if (++n > 90) clearInterval(connectPoll);
  }, 4000);
}
function renderTools() {
  const box = $("tool-rows"); box.replaceChildren();
  const tools = status.tools || {};
  for (const name of ["blender", "unity", "godot", "unreal"]) {
    const tl = tools[name]; if (!tl) continue;
    const row = el("div", "crow");
    row.append(el("b", "", name[0].toUpperCase() + name.slice(1)));
    const found = !!tl.path;
    let text = found ? `${tl.version || t("ready")}` : t("not_found");
    if (name === "blender" && found) text += ` · ${tl.addon ? t("addon_ok") : t("addon_missing")}`;
    const state = el("span", "state " + (found && (name !== "blender" || tl.addon) ? "ok" : "bad"), text);
    if (tl.how) state.append(el("small", "", tl.how));
    row.append(state);
    const acts = el("span", "acts");
    if (name === "blender" && found && !tl.addon) acts.append(btn(t("install_addon"), async () => {
      document.querySelector('[data-pane="log"]').click();
      try { await runJob(() => api("/api/install-addon", {})); status = await api("/api/status?refresh=1"); renderConnect(); }
      catch (e) { log({ stage: "error", message: e.message }); } finally { job = null; }
    }, "primary small"));
    if (!found && tl.url) acts.append(btn(t("download"), () => window.open(tl.url, "_blank")));
    if (tl.plugin) acts.append(btn(t("plugin_files"), () => api("/api/reveal-plugin", { tool: name }).catch((e) => log({ stage: "error", message: e.message }))));
    row.append(acts); box.append(row);
  }
}
function renderComponents() {
  const box = $("component-rows"); box.replaceChildren();
  for (const c of Object.values(status.components || {})) {
    const row = el("div", "crow");
    row.append(el("b", "", c.label));
    const state = el("span", "state " + (c.installed && !c.missing ? "ok" : "bad"),
      c.installed ? (c.missing ? t("comp_missing") : t("installed")) : t("not_installed"));
    state.append(el("small", "", `${c.what} · ${c.size} · ${c.gpu}`));
    state.append(el("small", "", c.license));
    if (c.installed && c.missing) state.append(el("small", "", c.missing));
    else if (!c.installed && c.extra_step) state.append(el("small", "", t("then") + " " + c.extra_step));
    row.append(state);
    const acts = el("span", "acts");
    if (!c.installed) acts.append(btn(t("install"), async () => {
      if (!confirm(`${c.label}: ${c.size}. ${t("install")}?`)) return;
      document.querySelector('[data-pane="log"]').click();
      try { await runJob(() => api("/api/setup", { provider: c.id })); status = await api("/api/status?refresh=1"); renderConnect(); renderProviders(); }
      catch (e) { log({ stage: "error", message: e.message }); } finally { job = null; }
    }));
    acts.append(btn(t("about"), () => window.open(c.url, "_blank")));
    row.append(acts); box.append(row);
  }
}
function renderConnect() {
  if (!status) return;
  renderTools();
  renderComponents();
  const cli = $("cli-rows"); cli.replaceChildren();
  for (const [name, path] of Object.entries(status.ai)) {
    const setup = status.setup?.[name] || {};
    const signed = status.signed_in?.[name];
    const row = el("div", "crow");
    row.append(el("b", "", name));
    const state = el("span", "state " + (path && signed !== false ? "ok" : "bad"),
      !path ? t("missing") : signed === false ? t("not_signed_in") : t("ready"));
    row.append(state);
    const acts = el("span", "acts");
    if (!path && setup.install) acts.append(status.npm ? btn(t("install"), () => openTerminal(name, "install")) : el("code", "", t("no_npm")));
    if (!path && setup.download) acts.append(btn(t("download"), () => window.open(setup.download, "_blank")));
    if (path && signed === false && setup.login) acts.append(btn(t("sign_in"), () => openTerminal(name, "login"), "primary small"));
    if (path && name === "ollama") acts.append(btn(setup.login.split(" ").slice(-1)[0], () => openTerminal(name, "login")));
    if (!path && setup.install) acts.append(el("code", "", setup.install));
    row.append(acts); cli.append(row);
  }
  const meshRows = $("mesh-rows"); meshRows.replaceChildren();
  for (const [id, p] of Object.entries(status.providers || {})) {
    if (id === "command") continue;
    const row = el("div", "crow");
    row.append(el("b", "", id));
    row.append(el("span", "state " + (p.ready ? "ok" : "bad"), p.ready ? `${t("ready")} · ${p.license}` : (p.key_env ? p.key_env : p.needs)));
    const acts = el("span", "acts");
    if (id === "triposr" && !p.ready) acts.append(btn(t("install"), () => { $("connect-dialog").close(); $("setup-triposr").click(); }, "primary small"));
    row.append(acts); meshRows.append(row);
  }
  const pic = el("div", "crow");
  const drawers = Object.entries(status.image_providers || {}).filter(([, ok]) => ok).map(([k]) => k);
  pic.append(el("b", "", t("pictures")), el("span", "state " + (drawers.length ? "ok" : "bad"), drawers.length ? drawers.join(", ") : t("concept_none")), el("span", "acts"));
  meshRows.append(pic);
  $("keys-where").textContent = `${t("keys_where")} ${status.keys_file}`;
  const keyRows = $("key-rows"); keyRows.replaceChildren();
  for (const [name, k] of Object.entries(status.keys || {})) {
    const row = el("div", "crow krow");
    const label = el("b", "", name); const what = el("small", "state", k.what); label.append(what);
    row.append(label);
    const input = el("input"); input.type = "password"; input.autocomplete = "off"; input.spellcheck = false;
    input.placeholder = k.set ? `${t("key_saved")} ${k.hint}${k.source === "env" ? " (env)" : ""}` : t("key_placeholder");
    row.append(input);
    const acts = el("span", "acts");
    acts.append(btn(t("save"), async () => {
      try { await api("/api/keys", { name, value: input.value }); input.value = ""; status = await api("/api/status?refresh=1"); renderConnect(); renderPills(); renderProviders(); }
      catch (e) { log({ stage: "error", message: e.message }); }
    }, "primary small"));
    if (k.set && k.source === "file") acts.append(btn(t("clear"), async () => { await api("/api/keys", { name, value: "" }); status = await api("/api/status?refresh=1"); renderConnect(); renderProviders(); }));
    const link = el("a", "", "↗"); link.href = k.url; link.target = "_blank"; link.rel = "noopener"; link.title = k.url; acts.append(link);
    row.append(acts); keyRows.append(row);
  }
  const anyAi = Object.entries(status.ai).some(([n, p]) => p && status.signed_in?.[n] !== false);
  $("connect").classList.toggle("attn", !anyAi);
}
$("connect").onclick = () => { renderConnect(); $("connect-dialog").showModal(); };
$("status-refresh").onclick = async () => { status = await api("/api/status?refresh=1").catch(() => status); renderConnect(); renderPills(); renderAi(); renderProviders(); };
$("connect-dialog").addEventListener("close", () => clearInterval(connectPoll));

// ---------------------------------------------------------------- viewer
async function ensureViewer() {
  if (viewer || viewerFailed) return viewer;
  try {
    const { createViewer } = await import("/viewer/meshgate-viewer.js");
    viewer = createViewer($("viewer"), { quality: "pc", variants: false, grid: true, autoplay: true,
      background: 0x111215, gridMajor: 0x46474b, gridMinor: 0x292a2e });
  } catch (e) {
    viewerFailed = true;   // offline or no WebGL: fall back to the rendered preview PNG
    console.warn("MeshGate viewer unavailable:", e);
  }
  return viewer;
}
async function show(item, tier) {
  $("base-comparison").classList.add("hidden");
  $("base-comparison-full").classList.add("hidden");
  $("base-status").textContent = item.saved_base ? t("base_source") + item.saved_base : "";
  current = item; currentTier = tier || item.canonical || Object.keys(item.tiers).pop();
  $("empty").classList.add("hidden");
  renderTierTabs(); renderLibrary();
  const entry = item.tiers[currentTier];
  const v = await ensureViewer();
  if (v && entry?.file) {
    $("still").classList.add("hidden");
    try { await v.load(fileUrl(item.name, entry.file), { name: entry.file }); v.setWireframe(wire); } catch (e) { console.warn(e); }
  } else if (item.preview) {
    $("still").src = fileUrl(item.name, item.preview); $("still").classList.remove("hidden");
  }
  if (!job) showHistory(item);
  collectParts(); collectLook(); renderClips(item); renderTune(item); renderParts(); renderDock(); renderLook();
  const clips = item.clips?.length ? ` · ${t("clips")}: ${item.clips.join(", ")}` : "";
  const how = item.engine === "mesh" ? `${t("engine_opts").mesh}${item.provider ? " · " + item.provider : ""}` : t("engine_opts").kit;
  const text = `${item.description || item.name}${clips} · ${how} · ${item.attempts} ${plural(item.attempts, t("attempts_forms"))}, ${item.seconds ?? "?"} ${t("seconds")}`;
  const ref = item.input_image || item.reference_image;
  $("info").replaceChildren();
  if (ref) { const img = document.createElement("img"); img.className = "ref"; img.alt = ""; img.src = fileUrl(item.name, ref); $("info").append(img); }
  $("info").append(document.createTextNode(text));
  if (item.code) {
    try { $("code").textContent = await (await fetch(fileUrl(item.name, item.code), { cache: "no-store" })).text(); } catch { /* ignore */ }
  }
}
function renderTierTabs() {
  const box = $("tier-tabs");
  if (!current) { box.replaceChildren(); return; }
  const order = ["pc", "mobile-high", "mobile-mid", "mobile-low"];
  const label = (id) => status?.tiers.find((x) => x.id === id)?.label || id;
  box.replaceChildren(...order.filter((id) => current.tiers[id]).map((id) => {
    const e = current.tiers[id]; const b = document.createElement("button");
    b.className = (id === currentTier ? "on " : "") + (e.within_budget ? "" : "over");
    b.setAttribute("role", "tab"); b.setAttribute("aria-selected", String(id === currentTier));
    b.setAttribute("aria-label", `${label(id)}: ${(e.tris || 0).toLocaleString()} ${t("tris")}`);
    b.innerHTML = `<b>${label(id)}</b><small>${(e.tris || 0).toLocaleString()} ${t("of")} ${(e.max_tris || 0).toLocaleString()} ${t("tris")}${e.within_budget ? "" : " · " + t("over")}</small>`;
    b.onclick = () => show(current, id);
    return b;
  }));
}
$("wire").onclick = () => { wire = !wire; viewer?.setWireframe(wire); $("wire").classList.toggle("on", wire); };
$("reveal").onclick = () => current && api("/api/reveal", { name: current.name }).catch((e) => log({ stage: "error", message: e.message }));

function showHistory(item) {
  $("log").replaceChildren();
  const who = item.engine === "mesh" ? `${t("engine_opts").mesh}${item.provider ? " · " + item.provider : ""}`
    : item.ai ? `${item.ai}${item.model ? " · " + item.model : ""}` : t("own_code");
  log({ stage: "start", message: `${item.name} — ${who}` });
  (item.history || []).forEach((a, i) => {
    log({ stage: a.ok ? "tier" : "problem", ok: a.ok, message: `${t("attempt")} ${i + 1}: ${a.ok ? "✓" : "✗"}` });
    a.problems.forEach((p) => log({ stage: "problem", message: "  " + p }));
  });
  const order = ["pc", "mobile-high", "mobile-mid", "mobile-low"].filter((id) => item.tiers[id]);
  order.forEach((id) => {
    const e = item.tiers[id];
    log({ stage: "tier", ok: e.within_budget, message: `${e.within_budget ? "✓" : "✗"} ${id}: ${(e.tris || 0).toLocaleString()} / ${(e.max_tris || 0).toLocaleString()} ${t("tris")}` });
  });
}

// ---------------------------------------------------------------- library
function renderLibrary() {
  const cards = $("cards");
  if (!library.length) { cards.innerHTML = `<span class="none">${t("nothing")}</span>`; return; }
  cards.replaceChildren(...library.map((item) => {
    const c = document.createElement("button"); c.type = "button";
    c.className = "card" + (item.ok ? "" : " bad") + (current?.name === item.name ? " on" : "");
    const img = item.preview ? `<img loading="lazy" alt="" src="${fileUrl(item.name, item.preview)}">` : `<div class="noimg"></div>`;
    const tris = item.tiers[item.canonical]?.tris;
    c.innerHTML = `${img}<b></b><small>${tris ? tris.toLocaleString() + " " + t("tris") : ""}</small>`;
    c.querySelector("b").textContent = item.name;
    c.title = item.description || item.name;
    c.onclick = () => show(item);
    return c;
  }));
}
async function refreshLibrary() { library = await api("/api/library"); renderLibrary(); }

// ---------------------------------------------------------------- generation
function log(ev) {
  const li = document.createElement("li");
  li.className = `${ev.stage || "log"}${ev.ok || ev.data?.within_budget ? " ok" : ""}`;
  li.textContent = (ev.message || "").trim();
  $("log").append(li); li.scrollIntoView({ block: "end" });
}
function busy(on) {
  if (current) setTimeout(renderDock);
  $("go").disabled = on; $("go").textContent = on ? t("generating") : t("generate");
  $("cancel").classList.toggle("hidden", !on);
  ["edit-go", "rebuild", "params-reset", "restore"].forEach((id) => { $(id).disabled = on; });
  meterReset(on);
}

// progress: the generator sends one `meter` event per step (pct at its start and end, its expected seconds, the
// seconds left); between events the bar creeps across the step by the clock, never past the step's end
let meterState = null, meterShown = 0, meterTimer = null;
function meterReset(on) {
  meterState = null; meterShown = 0;
  clearInterval(meterTimer); meterTimer = null;
  $("meter").classList.toggle("hidden", !on);
  $("meter-fill").style.width = "0%"; $("meter-step").textContent = on ? t("meter_start") : ""; $("meter-left").textContent = "";
  if (on) meterTimer = setInterval(meterTick, 500);
}
function meterEvent(ev) { meterState = { ...ev, t0: Date.now() }; meterTick(); }
function meterTick() {
  const m = meterState;
  if (!m) return;
  const el = (Date.now() - m.t0) / 1000;
  const inStep = m.step_s > 0 ? Math.min(0.95, el / m.step_s) : 0;
  meterShown = Math.max(meterShown, Math.min(100, m.pct + (m.pct_end - m.pct) * inStep));
  $("meter-fill").style.width = `${meterShown.toFixed(1)}%`;
  $("meter").setAttribute("aria-valuenow", String(Math.round(meterShown)));
  const left = Math.max(0, Math.round(m.eta - Math.min(el, m.step_s || el)));
  $("meter-step").textContent = m.step ? `${stepLabel(m.step)} · ${Math.round(meterShown)}%` : `${Math.round(meterShown)}%`;
  $("meter-left").textContent = meterShown >= 100 ? t("meter_done") : left > 0 ? `${t("meter_left")} ${fmtTime(left)}` : t("meter_soon");
}
function fmtTime(s) { return s >= 90 ? `~${Math.round(s / 60)} ${t("min")}` : `~${s} ${t("seconds")}`; }
function stepLabel(step) {
  const map = t("meter_steps");
  return step.replace(/^(review \d+|attempt \d+): /, (_, a) => `${a.replace("review", t("review_word")).replace("attempt", t("attempt_word"))}: `)
    .replace(/building (\S+)/, (_, tier) => `${map.building} ${status?.tiers.find((x) => x.id === tier)?.label || tier}`)
    .replace(/^asking the AI$/, map.ask).replace(/the AI compares$/, map.compare).replace(/^rendering$|rendering$/, map.render)
    .replace(/^drawing the concept$/, map.concept).replace(/^generating the 3D model$/, map.mesh).replace(/^8K master$/, map.master);
}
$("anim-on").onchange = () => { $("anim-box").classList.toggle("hidden", !$("anim-on").checked); if ($("anim-on").checked) $("anim").focus(); };
$("form").onsubmit = async (e) => {
  e.preventDefault();
  const checked = (id) => [...$(id).querySelectorAll("input:checked")].map((x) => x.value);
  if (!$("description").value.trim() && !picture && !model) { log({ stage: "error", message: t("need_input") }); return; }
  const req = {
    description: $("description").value, name: $("name").value, size: parseFloat($("size").value) || 0, style,
    image: picture, mesh: model, split: $("split").checked, engine, provider: $("provider").value, fal_model: $("fal_model").value, colors,
    concept: $("concept").checked && !picture && !model ? (engine === "mesh" ? "single" : "sheet") : "none",
    anim: $("anim-on").checked ? $("anim").value.trim() : "",
    texture: $("texture").value, topology: $("topology").value, pose: $("pose").value, outline: $("outline").value, pbr: $("pbr").checked,
    tris: tierPlan().tris,
    detail: parseFloat($("detail").value) || 1, turn: parseFloat($("turn").value) || 0,
    tiers: tierPlan().tiers, targets: checked("targets"), ai: $("ai").value, model: $("model").value,
    ai_cmd: $("ai_cmd").value, attempts: parseInt($("attempts").value, 10) || 3, review: parseInt($("review").value, 10) || 0, collision: $("collision").value,
  };
  $("log").replaceChildren(); $("code").textContent = "";
  document.querySelector('[data-pane="log"]').click();
  await followJob(() => api("/api/gen", req));
};

// run a job (generate or refine) and show its progress, then the result
async function followJob(start) {
  busy(true);
  try {
    job = await start();
    let since = 0;
    for (;;) {
      await new Promise((r) => setTimeout(r, 700));
      const s = await api(`/api/jobs/${job.id}?since=${since}`);
      s.lines.forEach((ev) => (ev.stage === "meter" ? meterEvent(ev) : log(ev))); since = s.next;
      if (s.done) { if (s.cancelled) log({ stage: "error", message: t("cancelled") }); break; }
    }
    await refreshLibrary();
    const made = library.find((i) => i.name === job.name);
    if (made) await show(made);
  } catch (err) {
    log({ stage: "error", message: err.message });
  } finally { busy(false); job = null; }
}

// ---------------------------------------------------------------- refine: words, sliders, versions, clips
function renderClips(item) {
  const box = $("clips");
  const clips = item?.clips || [];
  box.classList.toggle("hidden", !clips.length || !viewer);
  box.replaceChildren(...clips.map((name) => {
    const b = document.createElement("button"); b.className = "ghost"; b.textContent = name; b.title = t("clip_hint");
    b.onclick = () => {
      const on = !b.classList.contains("on");
      box.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      if (on) { b.classList.add("on"); viewer.animations.solo(name); viewer.animations.play(name); }
      else viewer.animations.stop();
    };
    return b;
  }));
}
function renderTune(item) {
  const kit = item && item.engine !== "mesh" && item.code;
  ["edit-go", "rebuild", "params-reset", "restore"].forEach((id) => { $(id).disabled = !kit || !!job; });
  $("tune-hint").textContent = !item ? "" : !kit ? t("tune_mesh_hint") : !(item.params || []).length ? t("tune_no_params") : "";
  $("params").replaceChildren(...(kit ? item.params || [] : []).map((p) => {
    const row = document.createElement("label"); row.className = "param";
    const step = p.step || (p.max - p.min) / 100;
    const fmt = (v) => (p.step && Number.isInteger(p.step) ? String(Math.round(v)) : (+v).toFixed(Math.abs(p.max - p.min) < 1 ? 3 : 2));
    row.innerHTML = `<span>${p.label}</span><output></output><input type="range" min="${p.min}" max="${p.max}" step="${step}" data-name="${p.name}" data-default="${p.default}">`;
    const r = row.querySelector("input"), o = row.querySelector("output");
    r.value = p.value ?? p.default; o.textContent = fmt(r.value);
    r.oninput = () => { o.textContent = fmt(r.value); };
    return row;
  }));
  const vs = kit ? item.versions || [] : [];
  $("versions").replaceChildren(...(vs.length ? vs : [null]).map((v) => {
    const o = document.createElement("option");
    if (!v) { o.textContent = t("tune_no_versions"); o.value = ""; return o; }
    const when = new Date(v.time * 1000).toLocaleString([], { hour: "2-digit", minute: "2-digit", day: "numeric", month: "short" });
    const what = v.edit ? `“${v.edit.slice(0, 40)}”` : Object.keys(v.params || {}).length ? t("tune_params").toLowerCase() : t("tune_first");
    o.value = v.id; o.textContent = `v${+v.id} · ${when} · ${what}`;
    return o;
  }));
  $("restore").disabled = !kit || !vs.length || !!job;
}
const sliderValues = () => Object.fromEntries([...document.querySelectorAll("#params input[type=range]")].map((r) => [r.dataset.name, +r.value]));
const refine = (extra) => current && followJob(() => api("/api/refine", { name: current.name, ...extra }))
  .then(() => document.querySelector('[data-pane="tune"]').click());
$("rebuild").onclick = () => { $("log").replaceChildren(); refine({ params: sliderValues() }); };
$("params-reset").onclick = () => document.querySelectorAll("#params input[type=range]").forEach((r) => { r.value = r.dataset.default; r.oninput(); });
$("edit-go").onclick = () => {
  const change = $("edit-text").value.trim();
  if (!change) { $("edit-text").focus(); return; }
  $("log").replaceChildren(); document.querySelector('[data-pane="log"]').click();
  refine({ change, params: sliderValues(), ai: $("ai").value, ai_cmd: $("ai_cmd").value, model: $("model").value });
};
$("restore").onclick = () => { const v = $("versions").value; if (v) { $("log").replaceChildren(); refine({ version: v }); } };
$("cancel").onclick = () => job && api(`/api/jobs/${job.id}/cancel`, {});

document.querySelectorAll(".tabs.small button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll(".tabs.small button").forEach((x) => x.classList.toggle("on", x === b));
    $("pane-log").classList.toggle("hidden", b.dataset.pane !== "log");
    $("pane-code").classList.toggle("hidden", b.dataset.pane !== "code");
    $("pane-tune").classList.toggle("hidden", b.dataset.pane !== "tune");
    $("pane-parts").classList.toggle("hidden", b.dataset.pane !== "parts");
    $("pane-look").classList.toggle("hidden", b.dataset.pane !== "look");
    if (b.dataset.pane === "look") renderLook();
    if (b.dataset.pane === "parts") renderParts(); else viewer?.setGizmo(null);
  };
});


// ---------------------------------------------------------------- parts: move, turn, scale, repaint, copy or remove
// the pieces of a split model by hand; saved as edits.json next to the model and rebuilt into every tier
let parts = [], partSel = null, partMode = "translate", partBase = new Map(), partDraft = {}, partsHooked = false;
let partMeta = new Map(), partHistory = [], newCopies = 0;
const PAINT = { red: "#b8423a", orange: "#d9822b", yellow: "#e3c34a", green: "#5f9a4a", teal: "#3f9a90", blue: "#3f6fb8",
  purple: "#7a4fa8", pink: "#d77fa1", brown: "#8a5a35", tan: "#c49a6c", white: "#e8e4dc", grey: "#8d8f93", black: "#2a2a2c" };
const yawOf = (o) => { const v = new viewer.THREE.Vector3(1, 0, 0).applyQuaternion(o.quaternion); return Math.atan2(-v.z, v.x); };
const isKit = () => current && current.engine !== "mesh" && current.palette?.length;
function collectParts() {
  const root = viewer?.model && current ? viewer.model.getObjectByName(current.name) : null;
  parts = root && root.children.length > 1 ? root.children.filter((o) => o.name) : [];
  partBase = new Map(parts.map((o) => [o.name, { p: o.position.clone(), yaw: yawOf(o), s: o.scale.x }]));
  partMeta = new Map();
  for (const o of parts) {   // copies saved earlier come back as <part>_copyN: their changes go to that copy's entry
    const m = /^(.+)_copy(\d+)$/.exec(o.name);
    if (m && current.part_edits?.[m[1]]?.copies?.[+m[2] - 1]) partMeta.set(o, { source: m[1], copy: +m[2] });
  }
  partDraft = {}; partSel = null; partHistory = []; viewer?.setGizmo(null);
  if (viewer && !partsHooked) {
    partsHooked = true;
    viewer.on("transform", () => renderParts());
    viewer.on("transform-start", () => snapshot());
    viewer.on("select", ({ object }) => {
      if ($("pane-parts").classList.contains("hidden")) return;
      let o = object;
      while (o && !parts.includes(o)) o = o.parent;
      partSel = o || null;
      viewer.setGizmo(partSel && !partDraft[partSel.name]?.delete ? partSel : null, partMode);
      renderParts();
    });
  }
}
function snapshot() {
  partHistory.push({ items: parts.map((o) => ({ o, p: o.position.clone(), q: o.quaternion.clone(), s: o.scale.clone(), v: o.visible })),
    draft: JSON.stringify(partDraft), sel: partSel });
  if (partHistory.length > 100) partHistory.shift();
}
function undoPart() {
  const h = partHistory.pop();
  if (!h) return;
  const keep = new Set(h.items.map((i) => i.o));
  for (const o of parts) if (!keep.has(o)) { o.parent?.remove(o); partMeta.delete(o); partBase.delete(o.name); }   // copies made since
  for (const i of h.items) { i.o.position.copy(i.p); i.o.quaternion.copy(i.q); i.o.scale.copy(i.s); i.o.visible = i.v; }
  parts = h.items.map((i) => i.o); partDraft = JSON.parse(h.draft);
  partSel = h.sel && parts.includes(h.sel) ? h.sel : null;
  viewer.select(partSel);
  if (!partSel) { viewer.setGizmo(null); renderParts(); }
}
function renderParts() {
  const item = current, can = !!item?.rebuildable, busyNow = !!job;
  $("parts-split").classList.toggle("hidden", !can || parts.length > 0);
  $("parts-split").disabled = busyNow;
  $("parts-hint").textContent = !item ? "" : !can ? t("parts_cannot") : parts.length ? t("parts_hint") : t("parts_none");
  $("parts-keys").classList.toggle("hidden", !parts.length);
  $("parts-list").replaceChildren(...parts.map((o) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = o.name;
    b.className = "ghost small part" + (o === partSel ? " on" : "") + (partDraft[o.name]?.delete ? " gone" : "")
      + (item.part_edits?.[o.name] || partChanged(o) ? " edited" : "");
    b.onclick = () => viewer.select(o);
    return b;
  }));
  $("part-tools").classList.toggle("hidden", !partSel);
  if (partSel) {
    const d = partDraft[partSel.name] || {}, meta = partMeta.get(partSel), kit = isKit();
    $("part-name").textContent = partSel.name;
    // kit: the model's own palette; a baked model: paint colours over its texture (not on copies, which share it)
    const choices = kit ? item.palette.map((c) => [c.name, c.name, c.hex]) : meta ? [] : Object.entries(PAINT).map(([n, hex]) => [hex, t("paint")[n] || n, hex]);
    $("part-colour").replaceChildren(...[["", t("part_as_built"), ""], ...choices].map(([v, label, hex]) => {
      const o = document.createElement("option"); o.value = v; o.textContent = label;
      if (hex) o.style.background = hex;
      return o;
    }));
    const saved = meta?.copy ? item.part_edits?.[meta.source]?.copies?.[meta.copy - 1] : item.part_edits?.[partSel.name];
    $("part-colour").value = d.colour || saved?.colour || "";
    $("part-colour").disabled = !choices.length; $("part-colour").title = choices.length ? "" : t("part_colour_mesh");
    $("part-delete").textContent = t(d.delete ? "part_restore" : "part_delete");
  }
  document.querySelectorAll("#part-mode button").forEach((b) => b.classList.toggle("on", b.dataset.mode === partMode));
  const dirty = parts.some((o) => partChanged(o));
  $("parts-save").disabled = !can || busyNow || !dirty;
  $("parts-undo").disabled = !partHistory.length;
  $("parts-clear").disabled = !can || busyNow || !Object.keys(item?.part_edits || {}).length;
}
function partChanged(o) {
  const meta = partMeta.get(o), d = partDraft[o.name] || {};
  if (meta?.fresh) return !d.delete;
  const b = partBase.get(o.name);
  if (!b) return false;
  return o.position.distanceTo(b.p) > 1e-5 || Math.abs(yawOf(o) - b.yaw) > 1e-4 || Math.abs(o.scale.x / b.s - 1) > 1e-4 || !!d.delete || !!d.colour;
}
function addDelta(e, o, b) {
  // moves add up, turns add, scales multiply; the view is Y-up, the model file Z-up: (x, y, z) here is (x, -z, y) there
  const dp = o.position.clone().sub(b.p), mv = e.move || [0, 0, 0];
  let turn = ((yawOf(o) - b.yaw) * 180) / Math.PI;
  turn = ((turn + 540) % 360) - 180;
  e.move = [mv[0] + dp.x, mv[1] - dp.z, mv[2] + dp.y];
  e.turn = (e.turn || 0) + turn; e.scale = (e.scale || 1) * (o.scale.x / b.s);
  return e;
}
function partEdits() {
  const saved = current.part_edits || {}, out = JSON.parse(JSON.stringify(saved));
  for (const o of parts) {
    if (!partChanged(o)) continue;
    const meta = partMeta.get(o), d = partDraft[o.name] || {};
    if (meta?.fresh) {   // a new copy: placed from its part as built — the part's saved change plus where it is now
      const s0 = saved[meta.source] || {};
      const e = addDelta({ move: [...(s0.move || [0, 0, 0])], turn: s0.turn || 0, scale: s0.scale || 1 }, o, partBase.get(meta.source));
      if (d.colour) e.colour = d.colour;
      ((out[meta.source] ||= {}).copies ||= []).push(e);
    } else if (meta?.copy) {   // a saved copy: its own entry
      const list = out[meta.source].copies;
      if (d.delete) list[meta.copy - 1] = null;
      else { addDelta(list[meta.copy - 1], o, partBase.get(o.name)); if (d.colour) list[meta.copy - 1].colour = d.colour; }
    } else {
      const e = addDelta(out[o.name] || {}, o, partBase.get(o.name));
      if (d.delete) e.delete = true;
      if (d.colour) e.colour = d.colour;
      out[o.name] = e;
    }
  }
  for (const e of Object.values(out)) if (e.copies) e.copies = e.copies.filter(Boolean);
  return out;
}
function duplicatePart() {
  if (!partSel || partDraft[partSel.name]?.delete) return;
  snapshot();
  const source = partMeta.get(partSel)?.source || partSel.name;
  const c = partSel.clone();
  const size = new viewer.THREE.Box3().setFromObject(partSel).getSize(new viewer.THREE.Vector3());
  c.position.x += size.x * 1.1;   // next to it, so both show
  c.name = `${source}_new${++newCopies}`;
  partSel.parent.add(c);
  parts.push(c); partMeta.set(c, { source, fresh: true });
  viewer.select(c);
}
function setPartMode(mode) {
  partMode = mode;
  if (partSel && !partDraft[partSel.name]?.delete) viewer.setGizmo(partSel, partMode);
  renderParts();
}
function togglePartDelete() {
  if (!partSel) return;
  snapshot();
  const d = (partDraft[partSel.name] ||= {});
  d.delete = !d.delete; partSel.visible = !d.delete;
  viewer.setGizmo(d.delete ? null : partSel, partMode); renderParts();
}
document.querySelectorAll("#part-mode button").forEach((b) => (b.onclick = () => setPartMode(b.dataset.mode)));
$("part-colour").onchange = () => { if (partSel) { snapshot(); (partDraft[partSel.name] ||= {}).colour = $("part-colour").value; renderParts(); } };
$("part-delete").onclick = togglePartDelete;
$("part-copy").onclick = duplicatePart;
$("parts-undo").onclick = undoPart;
$("part-reset").onclick = () => {
  if (!partSel) return;
  snapshot();
  const meta = partMeta.get(partSel);
  if (meta?.fresh) { partSel.parent.remove(partSel); parts = parts.filter((o) => o !== partSel); partSel = null; viewer.select(null); return; }
  const b = partBase.get(partSel.name);
  partSel.position.copy(b.p); partSel.scale.setScalar(b.s);
  partSel.quaternion.setFromAxisAngle(new viewer.THREE.Vector3(0, 1, 0), b.yaw);
  delete partDraft[partSel.name]; partSel.visible = true; viewer.select(partSel);
};
document.addEventListener("keydown", (e) => {   // W / E / R, ⌘/Ctrl+D, Delete, ⌘/Ctrl+Z — while the Parts tab is open
  if ($("pane-parts").classList.contains("hidden") || !parts.length || e.target.closest?.("input, textarea, select, [contenteditable]")) return;
  const mod = e.metaKey || e.ctrlKey, k = e.key.toLowerCase();
  if (mod && k === "z") { e.preventDefault(); undoPart(); }
  else if (mod && k === "d") { e.preventDefault(); duplicatePart(); }
  else if (mod) return;
  else if (k === "w") setPartMode("translate");
  else if (k === "e") setPartMode("rotate");
  else if (k === "r") setPartMode("scale");
  else if (k === "delete" || k === "backspace") { e.preventDefault(); togglePartDelete(); }
});
const rebuildParts = (extra) => { if (!current) return; $("log").replaceChildren(); viewer?.setGizmo(null); return refine(extra).then(() => document.querySelector('[data-pane="parts"]').click()); };
$("parts-save").onclick = () => rebuildParts({ parts: partEdits() });
$("parts-clear").onclick = () => rebuildParts({ parts: {} });
$("parts-split").onclick = () => rebuildParts({ split: true });

// ---------------------------------------------------------------- appearance: the model's morph targets as sliders and
// its palette as colours, both live in the view (like a game's character creator); saved as look.json and rebuilt
let lookMeshes = [], lookValues = {}, lookColours = {}, paletteTex = new Map();
function collectLook() {
  lookMeshes = [];
  viewer?.model?.traverse((o) => { if (o.isMesh && o.morphTargetDictionary) lookMeshes.push(o); });
  lookValues = { ...(current?.look?.morphs || {}) };
  lookColours = { ...(current?.look?.colours || {}) };
  paletteTex = new Map();
}
const hasMorph = (name) => lookMeshes.some((m) => name in m.morphTargetDictionary);
function setMorph(name, v) {
  lookValues[name] = v;
  for (const m of lookMeshes) {
    const d = m.morphTargetDictionary;
    if (name in d) m.morphTargetInfluences[d[name]] = Math.max(0, v);
    if (name + "_neg" in d) m.morphTargetInfluences[d[name + "_neg"]] = Math.max(0, -v);
  }
}
function paintPalette() {
  // kit models colour through one palette texture (a grid of cells): repaint the cells in a copy of it, live
  const grid = current?.palette_grid, cells = (current?.palette || []).filter((c) => lookColours[c.name]);
  if (!grid || !viewer?.model) return;
  viewer.model.traverse((o) => {
    if (!o.isMesh) return;
    for (const mat of Array.isArray(o.material) ? o.material : [o.material]) {
      const src = mat?.userData.mgPalette || mat?.map;
      if (!src?.image) continue;
      mat.userData.mgPalette = src;
      let tex = paletteTex.get(src.uuid);
      if (!tex) {
        const c = document.createElement("canvas"); c.width = src.image.width; c.height = src.image.height;
        tex = new viewer.THREE.CanvasTexture(c);
        Object.assign(tex, { flipY: src.flipY, colorSpace: src.colorSpace, wrapS: src.wrapS, wrapT: src.wrapT,
          magFilter: src.magFilter, minFilter: src.minFilter, generateMipmaps: src.generateMipmaps, channel: src.channel });
        paletteTex.set(src.uuid, tex);
      }
      const c = tex.image, g = c.getContext("2d"), px = c.width / grid;
      g.drawImage(src.image, 0, 0);
      for (const cell of cells) {   // Blender counts palette rows from the bottom, the image from the top
        g.fillStyle = lookColours[cell.name];
        g.fillRect((cell.index % grid) * px, (grid - 1 - Math.floor(cell.index / grid)) * px, px, px);
      }
      tex.needsUpdate = true;
      if (mat.map !== tex) { mat.map = tex; mat.needsUpdate = true; }
    }
  });
}
function renderLook() {
  const item = current;
  const morphs = (item?.morphs || []);
  $("look-hint").textContent = !item ? "" : morphs.length ? t("look_hint") : t("look_none");
  $("look-morphs").replaceChildren(...morphs.map((m) => {
    const row = document.createElement("label"); row.className = "param";
    const lo = m.two_sided === false ? 0 : -1, on = hasMorph(m.name);
    row.innerHTML = `<span></span><output></output><input type="range" min="${lo}" max="1" step="0.01">`;
    row.querySelector("span").textContent = m.label || m.name;
    const r = row.querySelector("input"), o = row.querySelector("output");
    r.value = lookValues[m.name] ?? 0; r.disabled = !on;
    o.textContent = on ? (+r.value).toFixed(2) : t("look_missing");
    r.oninput = () => { setMorph(m.name, +r.value); o.textContent = (+r.value).toFixed(2); };
    if (on) setMorph(m.name, +r.value);
    return row;
  }));
  const baked = item && !item.palette_grid;
  $("look-colours").replaceChildren(...(item?.palette || []).map((c) => {
    const row = document.createElement("label"); row.className = "look-colour";
    const inp = document.createElement("input"); inp.type = "color"; inp.value = lookColours[c.name] || c.hex;
    const name = document.createElement("span"); name.textContent = c.name.replace(/_/g, " ");
    inp.oninput = () => { lookColours[c.name] = inp.value; paintPalette(); };
    row.append(inp, name);
    return row;
  }));
  if (baked && item.palette?.length) { const n = document.createElement("small"); n.className = "hint"; n.textContent = t("look_baked"); $("look-colours").append(n); }
  paintPalette();
  const can = !!item?.rebuildable && item.engine !== "mesh" && !job;
  $("look-save").disabled = !can || (!morphs.length && !item?.palette?.length);
  $("look-random").disabled = !morphs.length;
  $("look-reset").disabled = !item;
}
$("look-random").onclick = () => {
  for (const m of current?.morphs || []) if (hasMorph(m.name)) lookValues[m.name] = +((Math.random() * 2 - 1) * (m.two_sided === false ? 0.5 : 0.8) + (m.two_sided === false ? 0.5 : 0)).toFixed(2);
  renderLook();
};
$("look-reset").onclick = () => {
  for (const m of current?.morphs || []) lookValues[m.name] = 0;
  lookColours = {};
  viewer?.model?.traverse((o) => { if (o.isMesh) for (const mat of Array.isArray(o.material) ? o.material : [o.material]) if (mat?.userData.mgPalette) { mat.map = mat.userData.mgPalette; mat.needsUpdate = true; } });
  paletteTex = new Map();
  renderLook();
};
$("look-save").onclick = () => {
  if (!current) return;
  const morphs = Object.fromEntries(Object.entries(lookValues).filter(([, v]) => Math.abs(v) > 1e-3));
  const colours = { ...lookColours };   // every colour set here (the palette already shows the ones saved before)
  $("log").replaceChildren();
  refine({ look: { morphs, colours } }).then(() => document.querySelector('[data-pane="look"]').click());
};

// ---------------------------------------------------------------- send to an engine project or Blender
let sendTool = null;
const fill = (text, vars) => text.replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? "");
async function sendModel(tool, project) {
  const got = await api("/api/send", { name: current.name, tool, project });
  status = await api("/api/status?refresh=1").catch(() => status);
  log({ stage: "done", ok: true, message: got.opened ? fill(t("send_opened"), { file: got.opened }) : fill(t("send_done"), { files: got.files.join(", "), folder: got.folder }) });
  document.querySelector('[data-pane="log"]').click();
}
async function openSend(tool) {
  if (!tool || !current) return;
  if (tool === "blender") { try { await sendModel(tool); } catch (e) { log({ stage: "error", message: e.message }); } return; }
  sendTool = tool;
  const name = { unity: "Unity", godot: "Godot", unreal: "Unreal" }[tool];
  $("send-title").textContent = fill(t("send_title"), { tool: name });
  $("send-where").textContent = t("send_where")[tool];
  $("send-project").value = status?.bridge?.[tool]?.project || "";
  $("send-error").textContent = "";
  $("send-dialog").showModal(); $("send-project").focus();
}
$("send-go").onclick = async () => {
  try { await sendModel(sendTool, $("send-project").value.trim()); $("send-dialog").close(); }
  catch (e) { $("send-error").textContent = e.message; }
};
$("send-project").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("send-go").click(); } });

// ---------------------------------------------------------------- hints: the text under a setting lives in an ⓘ next
// to its name, shown on hover, focus or a tap
function tipify(root = document) {
  root.querySelectorAll('small[data-i18n$="_hint"], small#engine-hint').forEach((small) => {
    if (small.closest(".tip")) return;
    const box = small.closest(".field, fieldset, .pop-field") || small.parentElement;
    let head = box.querySelector(":scope > span, :scope > legend");
    const prev = small.previousElementSibling;
    if (prev?.matches("label.check")) head = prev.querySelector("span");   // a checkbox: the ⓘ goes after its words
    if (!head) return;
    const tip = document.createElement("span");
    tip.className = "tip"; tip.tabIndex = 0; tip.setAttribute("role", "button"); tip.setAttribute("aria-label", "?");
    tip.textContent = "i";
    small.classList.add("tip-pop"); document.body.append(small);   // at the top level: no panel clips or shifts it
    if (head.dataset.i18n) {   // the words move into their own span, so a language switch keeps the ⓘ
      const words = document.createElement("span");
      words.dataset.i18n = head.dataset.i18n; words.textContent = head.textContent;
      delete head.dataset.i18n; head.replaceChildren(words);
    }
    head.append(tip);
    const show = (on) => {
      small.classList.toggle("show", on); tip.classList.toggle("open", on);
      if (!on) return;
      const r = tip.getBoundingClientRect(), w = Math.min(280, innerWidth - 16);
      small.style.width = `${w}px`;
      small.style.left = `${Math.max(8, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 8))}px`;
      const h = small.offsetHeight;
      small.style.top = `${r.bottom + 8 + h > innerHeight - 8 ? r.top - h - 8 : r.bottom + 8}px`;
    };
    tip.addEventListener("mouseenter", () => show(true)); tip.addEventListener("mouseleave", () => show(false));
    tip.addEventListener("focus", () => show(true)); tip.addEventListener("blur", () => show(false));
    tip.addEventListener("click", (e) => { e.preventDefault(); e.stopPropagation(); show(!small.classList.contains("show")); });
  });
}

// ---------------------------------------------------------------- the dock under the model: remesh, UV, texture,
// parts, send to an engine, download — each rebuilds or acts on the model in view
const dockPick = { tris: null, topology: "tri", texture: "auto", colors: "texture" };
function seg(id, options, key, onPick) {
  $(id).replaceChildren(...options.map(([v, label]) => {
    const b = document.createElement("button"); b.type = "button"; b.textContent = label;
    b.className = dockPick[key] === v ? "on" : "";
    b.onclick = () => { dockPick[key] = v; seg(id, options, key, onPick); onPick?.(); };
    return b;
  }));
}
function closePops(except) {
  document.querySelectorAll(".dock-pop").forEach((p) => p !== except && p.classList.add("hidden"));
  document.querySelectorAll(".tip-pop.show").forEach((p) => p.classList.remove("show"));
}
const remeshWarn = () => $("remesh-warn").classList.toggle("hidden", !(dockPick.topology === "quad" && dockPick.tris && dockPick.tris < 8000));
function openPop(id) {
  const pop = $(id), open = pop.classList.contains("hidden");
  closePops(); if (!open) return;
  renderDock(); pop.classList.remove("hidden");
}
function renderDock() {
  const it = current;
  $("dock").classList.toggle("hidden", !it);
  if (!it) return;
  const can = !!it.rebuildable && !job, st = it.settings || {};
  Object.assign(dockPick, { tris: st.tris ?? null, topology: st.topology || "tri", texture: st.texture || "auto", colors: st.colors || "texture" });
  seg("remesh-tris", [[null, t("dock_default")], [3000, "3K"], [10000, "10K"], [30000, "30K"], [100000, "100K"]], "tris", remeshWarn);
  seg("remesh-topo", [["quad", t("topo_quad")], ["tri", t("topo_tri")]], "topology", remeshWarn);
  remeshWarn();
  seg("tex-size", [["auto", t("auto")], ["1k", "1K"], ["2k", "2K"], ["4k", "4K"], ["8k", "8K"]], "texture");
  seg("tex-colors", [["texture", t("colors_opts")?.texture || "Textures"], ["vertex", t("colors_opts")?.vertex || "Vertex"]], "colors");
  $("tex-pbr").checked = !!st.pbr;
  const e = it.tiers[currentTier] || {};
  const tierName = status?.tiers.find((x) => x.id === currentTier)?.label || currentTier;
  $("remesh-note").textContent = it.rebuildable ? fill(t("dock_now"), { tris: (e.tris || 0).toLocaleString(), tier: tierName }) : t("dock_no_source");
  ["remesh-go", "uv-go", "tex-go"].forEach((id) => { $(id).disabled = !can; });
  $("uv-show").textContent = t(uvOn ? "dock_uv_hide" : "dock_uv_show");
  $("pop-download").replaceChildren(...(it.files || []).map((f) => {
    const a = document.createElement("a"); a.href = fileUrl(it.name, f); a.download = f; a.textContent = f;
    a.onclick = () => closePops();
    return a;
  }));
}
let uvOn = false;
document.querySelectorAll("[data-pop]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); openPop(b.dataset.pop); }));
document.querySelectorAll("[data-open]").forEach((b) => (b.onclick = (e) => { e.stopPropagation(); openPop(b.dataset.open); }));
document.querySelectorAll(".dock-pop").forEach((p) => p.addEventListener("click", (e) => e.stopPropagation()));
document.addEventListener("click", () => closePops());
window.addEventListener("scroll", () => document.querySelectorAll(".tip-pop.show").forEach((p) => p.classList.remove("show")), true);
document.querySelectorAll("[data-send]").forEach((b) => (b.onclick = () => { closePops(); openSend(b.dataset.send); }));
$("dock-parts").onclick = (e) => { e.stopPropagation(); closePops(); const tab = document.querySelector('[data-pane="parts"]'); tab.click(); tab.scrollIntoView({ block: "nearest" }); };
$("uv-show").onclick = () => { uvOn = !uvOn; viewer?.setUvChecker(uvOn); renderDock(); };
const rebuildWith = (settings) => { closePops(); $("log").replaceChildren(); refine({ settings }); };
$("remesh-go").onclick = () => rebuildWith({ tris: dockPick.tris, topology: dockPick.topology });
$("uv-go").onclick = () => rebuildWith({ topology: current?.settings?.topology || "tri" });
$("tex-go").onclick = () => rebuildWith({ texture: dockPick.texture, colors: dockPick.colors, pbr: $("tex-pbr").checked });
tipify();

// ---------------------------------------------------------------- start
(async () => {
  applyLang();
  try {
    status = await api("/api/status");
    renderPills(); renderAi(); renderTiers(); renderProviders(); renderConnect();
    await refreshLibrary();
    if (library[0]) show(library[0]);
  } catch (e) {
    $("pills").innerHTML = `<span class="pill bad">${e.message}</span>`;
  }
})();

for (const action of ["load", "save", "undo", "compare"]) {
  $("base-" + action).onclick = async () => {
    if (!current) return;
    if (job) return;
    const targetName = current.name;
    const buttons = ["load", "save", "undo", "compare"].map(a => $("base-" + a));
    buttons.forEach(b => b.disabled = true);
    $("base-status").textContent = "Blender…";
    try {
      const result = await api("/api/live-base", {name: targetName, action});
      if (current?.name !== targetName) return;
      if (result.image) {
        $("base-comparison").src = fileUrl(targetName, result.image);
        $("base-comparison").classList.remove("hidden");
        $("base-comparison-full").href = fileUrl(targetName, result.image);
        $("base-comparison-full").classList.remove("hidden");
      }
      if (result.active_base) current.saved_base = result.active_base;
      $("base-status").textContent = result.active_base ? t("base_saved") : result.image ? t("base_report") : result.path || t(action === "load" ? "base_loaded" : "base_undone");
    } catch (error) { if (current?.name === targetName) $("base-status").textContent = error.message; }
    finally { buttons.forEach(b => b.disabled = false); }
  };
}
