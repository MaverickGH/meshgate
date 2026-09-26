**English** · [Русский](meshgate_retarget.ru.md)

# Humanoid in Unreal: from `meshgate_hero` to UE5 Mannequin

The character's bones are named per Unity Humanoid (`Hips`, `Spine`, `Chest`, `LeftUpperArm`, …). In UE5 the character and its clips
are transferred to Manny/Quinn via IK Rig + IK Retargeter, and the names make it possible to build the chains without manual mapping:

1. Import `meshgate_hero.fbx` as a Skeletal Mesh (`meshgate_import.import_fbx(..., skeletal=True)`) — you get
   `SK_meshgate_hero`, `meshgate_hero_Skeleton`, and the `idle`, `wave` clips.
2. Create an **IK Rig** for `SK_meshgate_hero`: Retarget Root = `Hips`; chains: Spine (`Spine`→`Chest`),
   Head (`Neck`→`Head`), LeftArm (`LeftUpperArm`→`LeftHand`), RightArm, LeftLeg (`LeftUpperLeg`→`LeftFoot`), RightLeg,
   LeftClavicle (`LeftShoulder`), RightClavicle.
3. Create an **IK Retargeter**: Source = the hero's IK Rig, Target = `IK_Mannequin`. Chains with identical names
   are matched automatically (Auto-Map Chains → Exact/Fuzzy).
4. In the Retargeter, select `wave` → Export Selected Animations — you get a clip on Manny.

The reverse direction (Manny clip → hero) — with the same Retargeter, swapping Source/Target.
