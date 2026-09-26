[English](README.md) · **Русский**

# com.meshgate.unity

UPM-пакет: загрузка канонического GLB MeshGate в Unity поверх [Unity glTFast](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@latest) (Apache-2.0).

## Установка

Package Manager → **Add package from git URL**:

```
https://github.com/MaverickGH/meshgate.git?path=targets/unity/com.meshgate.unity
```

или локально в `Packages/manifest.json`: `"com.meshgate.unity": "file:../../com.meshgate.unity"`. Зависимость `com.unity.cloud.gltfast` подтянется сама из реестра Unity.

## Компоненты

| Компонент | Что делает |
|---|---|
| `MeshGateAsset` | Грузит `.glb` (StreamingAssets / абсолютный путь / http) в рантайме: иерархия с именами из glTF, `Find("crate_lid")`, анимации по именам (`Play`, `Solo`, `Stop`, `SetSpeed`), `Bounds`, счётчики мешей/трисов/материалов, коллайдеры (Box / Mesh / MeshConvex), события `onLoaded` / `onFailed`. |
| `MeshGateInteraction` | Наведение и клик по нодам с подсветкой и UnityEvent'ами — как во веб-вьюере. |
| `MeshGateOrbitCamera` | Орбитальная камера: ЛКМ — орбита, ПКМ — панорама, колесо — зум, `F` — кадрировать; сама кадрирует ассет после загрузки. |
| Меню **MeshGate → Validate Selected GLB** | Запускает `core/validate_glb.py` из репозитория и показывает отчёт. |
| `MeshGateFbxMaterials` (AssetPostprocessor) | Для FBX из Blender (`--fbx`): раскладывает Phong-описание по слотам Standard/URP Lit — альбедо, normal, эмиссия, metallic, smoothness; текстуры находит среди извлечённых. Срабатывает на FBX с «meshgate» в имени или на всех при `MeshGateFbxMaterials.applyToAll = true`. |

```csharp
var asset = gameObject.AddComponent<MeshGateAsset>();
asset.source = "meshgate_demo.glb";           // Assets/StreamingAssets/meshgate_demo.glb
asset.colliders = MeshGateColliders.Mesh;
asset.onLoaded.AddListener(a => {
    Debug.Log($"{a.MeshCount} мешей, {a.TriangleCount} трис, габариты {a.Bounds.size}");
    a.Solo("lid_open");                       // только один клип
    a.Find("beacon_ring").gameObject.SetActive(false);
});
```

Импорт в редакторе (перетащить `.glb` в `Assets/`) делает сам glTFast — получается префаб-подобный ассет с той же иерархией и Legacy-клипами.

## Контракт → Unity

- Метры и Y-up glTF совпадают с Unity; glTFast переводит правостороннюю систему в левостороннюю (зеркалит X), названия и иерархия сохраняются.
- PBR `metallicRoughness` → шейдеры glTFast для Built-in / URP / HDRP (выбираются по активному пайплайну).
- Draco / KTX2 / meshopt — нужны дополнительные пакеты `com.unity.cloud.draco`, `com.unity.cloud.ktx`, `com.unity.meshopt.decompress`; без них грузите несжатый вариант.
- Анимации — Legacy `Animation` (клип = имя анимации glTF). Для Mecanim поставьте `ImportSettings.AnimationMethod = Mecanim` и свой контроллер.

Ограничения: Legacy-анимации не работают с Timeline; `MeshGateInteraction`/`MeshGateOrbitCamera` используют старый Input Manager (`ENABLE_LEGACY_INPUT_MANAGER`).
