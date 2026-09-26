"""UI translations. Blender shows them when Preferences → Interface → Translation is set to the language
(and «Interface» is ticked under «Affect»). Keys are the English strings used in the UI."""

_RU = {
    # panel
    "Targets": "Цели", "Folder": "Папка", "Name": "Имя", "Selected only": "Только выделенное", "Animations": "Анимации",
    "FBX too": "Ещё и FBX", "Draco for web": "Draco для веба", "Textures": "Текстуры", "As is": "Как есть",
    "Check": "Проверить", "Fix all": "Исправить всё", "Export": "Экспорт", "Fix": "Исправить",
    "Contract satisfied": "Контракт соблюдён", "Report": "Отчёт", "Preview in browser": "Открыть в браузере",
    "Open folder": "Открыть папку", "Engine extras": "Для движков", "Collision": "Коллизия",
    "Convex hull": "Выпуклая оболочка", "Box": "Коробка", "Add collision": "Добавить коллизию", "Make LODs": "Сделать LOD",
    "%d collision proxies, %d LOD meshes in the scene": "В сцене: коллизий %d, LOD-мешей %d",
    "Quality tiers": "Уровни качества", "Low": "Слабые", "Mid": "Средние", "High": "Мощные",
    "Mobile low": "Мобильные: слабые", "Mobile mid": "Мобильные: средние", "Mobile high": "Мобильные: мощные",
    "PC = the canonical GLB (full quality)": "PC = канонический GLB (полное качество)",
    # reports
    "MeshGate: %d errors, %d warnings": "MeshGate: ошибок %d, предупреждений %d",
    "MeshGate: contract satisfied": "MeshGate: контракт соблюдён", "nothing to fix": "исправлять нечего",
    "MeshGate: %d files written to %s": "MeshGate: записано файлов %d в %s",
    "Save the .blend first, or choose an absolute export folder": "Сначала сохраните .blend или укажите абсолютную папку экспорта",
    "MeshGate: %d collision proxies": "MeshGate: коллизий создано %d", "MeshGate: %d LOD meshes": "MeshGate: LOD-мешей создано %d",
    # issues
    "Nothing to export: no visible, renderable meshes": "Нечего экспортировать: нет видимых мешей с включённым рендером",
    "Scene units are not meters (Metric, unit scale 1.0)": "Единицы сцены не метры (Metric, масштаб 1.0)",
    "Unapplied scale": "Не применён масштаб", "Negative scale flips normals in engines": "Отрицательный масштаб переворачивает нормали в движках",
    "Names with spaces or non-Latin characters": "Имена с пробелами или не латиницей", "Meshes without UVs": "Меши без UV",
    "Meshes without a material (engines show default grey)": "Меши без материала (в движке будут серыми)",
    "Materials without Principled BSDF — bake them to textures first": "Материалы без Principled BSDF — сначала запеките их в текстуры",
    "Texture files not found": "Файлы текстур не найдены",
    "Textures are external files — packing keeps the .blend self-contained": "Текстуры лежат снаружи — упаковка делает .blend самодостаточным",
    "Textures not power of two": "Текстуры не степени двойки", "Textures larger than 4096": "Текстуры больше 4096",
    "Skinned meshes with unweighted vertices (they stay behind when animated)": "В скин-мешах есть вершины без весов (при анимации останутся на месте)",
    "Active actions next to NLA clips — push them to NLA so every clip keeps its name": "Активные действия рядом с NLA-клипами — уберите их в NLA, чтобы имена клипов сохранились",
    "Visible but disabled for render — will not be exported": "Видимы, но выключены для рендера — не экспортируются",
    # properties
    "Where to write the files (// = next to the .blend)": "Куда писать файлы (// — рядом с .blend)",
    "File name without extension; empty = .blend name": "Имя файла без расширения; пусто — имя .blend",
}

DICT = {"ru_RU": {("*", k): v for k, v in _RU.items()}}
DICT["ru_RU"].update({("Operator", k): v for k, v in _RU.items()})
