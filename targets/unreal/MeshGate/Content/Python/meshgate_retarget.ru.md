[English](meshgate_retarget.md) · **Русский**

# Humanoid в Unreal: от `meshgate_hero` к UE5 Mannequin

Кости персонажа названы по Unity Humanoid (`Hips`, `Spine`, `Chest`, `LeftUpperArm`, …). В UE5 персонаж и его клипы
переносятся на Manny/Quinn через IK Rig + IK Retargeter, и имена позволяют собрать цепочки без ручного маппинга:

1. Импорт `meshgate_hero.fbx` как Skeletal Mesh (`meshgate_import.import_fbx(..., skeletal=True)`) — получите
   `SK_meshgate_hero`, `meshgate_hero_Skeleton`, клипы `idle`, `wave`.
2. Создайте **IK Rig** для `SK_meshgate_hero`: Retarget Root = `Hips`; цепочки: Spine (`Spine`→`Chest`),
   Head (`Neck`→`Head`), LeftArm (`LeftUpperArm`→`LeftHand`), RightArm, LeftLeg (`LeftUpperLeg`→`LeftFoot`), RightLeg,
   LeftClavicle (`LeftShoulder`), RightClavicle.
3. Создайте **IK Retargeter**: Source = IK Rig героя, Target = `IK_Mannequin`. Цепочки с одинаковыми именами
   сопоставляются автоматически (Auto-Map Chains → Exact/Fuzzy).
4. В Retargeter выберите `wave` → Export Selected Animations — получите клип на Manny.

Обратно (клип Manny → hero) — тем же Retargeter'ом с обменом Source/Target.
