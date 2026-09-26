// MeshGate — builds the demo scene in any project: copies samples/meshgate_demo.{glb,fbx} from the repository
// (or a given folder), imports them in the editor, and assembles the "FBX · glTF import · runtime" scene.
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace MeshGate.Editor
{
    public static class MeshGateDemoScene
    {
        public const string GlbName = "meshgate_demo.glb";
        public const string FbxName = "meshgate_demo.fbx";
        public const string HeroGlbName = "meshgate_hero.glb";
        public const string HeroFbxName = "meshgate_hero.fbx";
        public static string HeroGlbAssetPath => AssetDir + "/" + HeroGlbName;
        /// <summary>Extra props: loaded at runtime in a row in front of the crates (if the files exist in samples/).</summary>
        public static readonly string[] Props = { "meshgate_lantern.glb", "meshgate_barrel.glb", "meshgate_drone.glb" };
        public static string HeroFbxAssetPath => AssetDir + "/" + HeroFbxName;
        public const string AssetDir = "Assets/MeshGate";
        public const string ScenePath = AssetDir + "/MeshGateDemo.unity";
        public static string GlbAssetPath => AssetDir + "/" + GlbName;
        public static string FbxAssetPath => AssetDir + "/" + FbxName;

        [MenuItem("MeshGate/Build Demo Scene (from repo samples)")]
        public static void BuildFromRepo()
        {
            var root = MeshGateMenu.FindRepoRoot();
            if (root == null)
            {
                var dir = EditorUtility.OpenFolderPanel("Folder containing meshgate_demo.glb (samples/ of the MeshGate repository)", "", "");
                if (string.IsNullOrEmpty(dir)) return;
                Build(dir);
                return;
            }
            Build(Path.Combine(root, "samples"));
        }

        /// <summary>Copy the demo assets from a folder, import them, build and save the scene.</summary>
        public static void Build(string samplesDir)
        {
            CopyAssets(samplesDir);
            BuildScene();
        }

        public static void CopyAssets(string samplesDir)
        {
            var glb = Path.Combine(samplesDir, GlbName);
            if (!File.Exists(glb)) throw new FileNotFoundException("MeshGate: missing " + glb + " — export it from Blender (export_meshgate.py --fbx)");
            Directory.CreateDirectory(Path.Combine(Application.dataPath, "StreamingAssets"));
            Directory.CreateDirectory(Path.GetFullPath(AssetDir));
            File.Copy(glb, Path.Combine(Application.dataPath, "StreamingAssets", GlbName), true);   // runtime loading
            File.Copy(glb, Path.GetFullPath(GlbAssetPath), true);                                    // editor import (glTFast)
            var fbx = Path.Combine(samplesDir, FbxName);
            if (File.Exists(fbx)) File.Copy(fbx, Path.GetFullPath(FbxAssetPath), true);              // fallback path: native FBX
            // character: rigged humanoid — GLB for runtime, FBX as a Humanoid avatar
            var heroGlb = Path.Combine(samplesDir, HeroGlbName);
            if (File.Exists(heroGlb))
            {
                File.Copy(heroGlb, Path.Combine(Application.dataPath, "StreamingAssets", HeroGlbName), true);
                File.Copy(heroGlb, Path.GetFullPath(HeroGlbAssetPath), true);
            }
            var heroFbx = Path.Combine(samplesDir, HeroFbxName);
            if (File.Exists(heroFbx)) File.Copy(heroFbx, Path.GetFullPath(HeroFbxAssetPath), true);
            foreach (var prop in Props)
            {
                var src = Path.Combine(samplesDir, prop);
                if (File.Exists(src)) File.Copy(src, Path.Combine(Application.dataPath, "StreamingAssets", prop), true);   // for runtime and tests
                var propFbx = Path.Combine(samplesDir, Path.ChangeExtension(prop, ".fbx"));
                if (File.Exists(propFbx)) File.Copy(propFbx, Path.GetFullPath(AssetDir + "/" + Path.GetFileName(propFbx)), true);   // visible in the editor without Play
            }
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            ExtractFbxTextures(FbxAssetPath, AssetDir + "/meshgate_demo_textures");
            ExtractFbxTextures(HeroFbxAssetPath, AssetDir + "/meshgate_hero_textures");
            SetupHumanoid(HeroFbxAssetPath);
            foreach (var prop in Props)
            {
                var name = Path.GetFileNameWithoutExtension(prop);
                ExtractFbxTextures(AssetDir + "/" + name + ".fbx", AssetDir + "/" + name + "_textures");
            }
        }

        /// <summary>Character FBX → Mecanim Humanoid: the avatar is built from Unity Humanoid bone names.</summary>
        public static void SetupHumanoid(string fbxPath)
        {
            if (!(AssetImporter.GetAtPath(fbxPath) is ModelImporter importer)) return;
            if (importer.animationType == ModelImporterAnimationType.Human) return;
            importer.animationType = ModelImporterAnimationType.Human;
            importer.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
            importer.SaveAndReimport();
        }

        /// <summary>Unity does not assign FBX-embedded textures to materials until they are extracted.</summary>
        public static void ExtractFbxTextures() => ExtractFbxTextures(FbxAssetPath, AssetDir + "/meshgate_demo_textures");

        public static void ExtractFbxTextures(string fbxPath, string texDir)
        {
            if (!(AssetImporter.GetAtPath(fbxPath) is ModelImporter importer)) return;
            Directory.CreateDirectory(Path.GetFullPath(texDir));
            importer.ExtractTextures(texDir);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            var map = importer.GetExternalObjectMap();
            foreach (var guid in AssetDatabase.FindAssets("t:Texture", new[] { texDir }))
            {
                var texPath = AssetDatabase.GUIDToAssetPath(guid);
                var id = new AssetImporter.SourceAssetIdentifier(typeof(Texture), Path.GetFileNameWithoutExtension(texPath));
                if (!map.ContainsKey(id)) importer.AddRemap(id, AssetDatabase.LoadAssetAtPath<Texture>(texPath));
            }
            importer.SaveAndReimport();
        }

        public static void BuildScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.043f, 0.055f, 0.09f);
            cam.fieldOfView = 45f;
            camGo.transform.position = new Vector3(2.5f, 1.8f, -3f);
            camGo.transform.LookAt(Vector3.zero);
            var orbit = camGo.AddComponent<MeshGateOrbitCamera>();

            var lightGo = new GameObject("Key Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.6f;
            light.shadows = LightShadows.Soft;
            lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.55f, 0.6f, 0.75f);
            RenderSettings.ambientEquatorColor = new Color(0.3f, 0.32f, 0.4f);
            RenderSettings.ambientGroundColor = new Color(0.1f, 0.1f, 0.15f);

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.localScale = Vector3.one * 0.6f;
            var groundMat = new Material(ground.GetComponent<Renderer>().sharedMaterial) { color = new Color(0.12f, 0.13f, 0.2f) };
            ground.GetComponent<Renderer>().sharedMaterial = groundMat;

            // Left — FBX (native import), center — GLB via glTFast, right — the same GLB loaded at runtime.
            var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(FbxAssetPath);
            if (fbx)
            {
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(fbx);
                inst.name = "MeshGate Asset (FBX import)";
                inst.transform.position = new Vector3(-1.2f, 0f, 0f);
            }
            var imported = AssetDatabase.LoadAssetAtPath<GameObject>(GlbAssetPath);
            if (imported)
            {
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(imported);
                inst.name = "MeshGate Asset (editor import)";
                inst.transform.position = Vector3.zero;
            }
            else Debug.LogWarning("MeshGate: glTFast did not import " + GlbAssetPath);

            var runtimeGo = new GameObject("MeshGate Asset (runtime)");
            runtimeGo.transform.position = new Vector3(1.2f, 0f, 0f);
            var asset = runtimeGo.AddComponent<MeshGateAsset>();
            asset.source = GlbName;
            asset.colliders = MeshGateColliders.Mesh;
            runtimeGo.AddComponent<MeshGateInteraction>();
            orbit.target = asset;

            // Character behind the crates: left — FBX as Humanoid (Mecanim), right — the same GLB at runtime (Legacy clips).
            var heroFbx = AssetDatabase.LoadAssetAtPath<GameObject>(HeroFbxAssetPath);
            if (heroFbx)
            {
                var holder = new GameObject("MeshGate Hero (FBX Humanoid)");
                holder.transform.position = new Vector3(-0.7f, 0f, 1.2f);
                holder.transform.rotation = Quaternion.Euler(0f, 180f, 0f);   // facing the camera
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(heroFbx);
                inst.transform.SetParent(holder.transform, false);
                if (!inst.TryGetComponent<Animator>(out var animator)) animator = inst.AddComponent<Animator>();
                var clips = AssetDatabase.LoadAllAssetsAtPath(HeroFbxAssetPath).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__")).ToArray();
                var wave = clips.FirstOrDefault(c => c.name == "wave") ?? clips.FirstOrDefault();
                if (wave)
                {
                    var controllerPath = AssetDir + "/MeshGateHero.controller";
                    var controller = UnityEditor.Animations.AnimatorController.CreateAnimatorControllerAtPathWithClip(controllerPath, wave);
                    animator.runtimeAnimatorController = controller;
                }
            }
            if (File.Exists(Path.Combine(Application.dataPath, "StreamingAssets", HeroGlbName)))
            {
                var heroGo = new GameObject("MeshGate Hero (runtime)");
                heroGo.transform.position = new Vector3(0.7f, 0f, 1.2f);
                heroGo.transform.rotation = Quaternion.Euler(0f, 180f, 0f);
                var hero = heroGo.AddComponent<MeshGateAsset>();
                hero.source = HeroGlbName;
                heroGo.AddComponent<MeshGateInteraction>();
            }

            // Row of props in front of the crates: hanging lantern, barrel, drone — editor-imported FBX
            // (visible without Play). Runtime loading of the same GLBs is covered by the crate, the hero and PlayMode tests.
            var x = -1.2f;
            foreach (var prop in Props)
            {
                var name = Path.GetFileNameWithoutExtension(prop);
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(AssetDir + "/" + name + ".fbx");
                if (!prefab) continue;
                // Blender FBX carries animation keys on the root object too — the Animator would overwrite the root position.
                // So the instance lives under an empty parent, and that parent is what we position.
                var holder = new GameObject("MeshGate Prop FBX (" + name.Replace("meshgate_", "") + ")");
                holder.transform.position = new Vector3(x, prop.Contains("lantern") ? 1.0f : 0f, -1.3f);
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab);
                inst.transform.SetParent(holder.transform, false);
                x += 1.2f;
                var clips = AssetDatabase.LoadAllAssetsAtPath(AssetDir + "/" + name + ".fbx").OfType<AnimationClip>().Where(c => !c.name.StartsWith("__")).ToArray();
                if (clips.Length > 0)   // first clip goes into an Animator so the prop also moves in Play mode
                {
                    if (!inst.TryGetComponent<Animator>(out var animator)) animator = inst.AddComponent<Animator>();
                    animator.runtimeAnimatorController = UnityEditor.Animations.AnimatorController.CreateAnimatorControllerAtPathWithClip(AssetDir + "/" + name + ".controller", clips[0]);
                }
            }

            new GameObject("MeshGate HUD").AddComponent<MeshGateHud>();

            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log("MeshGate: demo scene saved → " + ScenePath);
        }

        // --------------------------------------------------------------------------------------------
        // Example pack: samples/packs/zombie_cats → Assets/MeshGate/Packs/zombie_cats + ZombieCats_Low/_Mid/_PC.unity
        // --------------------------------------------------------------------------------------------
        public const string PackName = "zombie_cats";
        public static string PackAssetDir => AssetDir + "/Packs/" + PackName;
        public static string PackScenePath => PackScenePathFor(MeshGateTier.PC);
        /// <summary>Three scenes of the same street at different quality: mobile-low, mobile-mid, pc.</summary>
        public static readonly MeshGateTier[] PackSceneTiers = { MeshGateTier.MobileLow, MeshGateTier.MobileMid, MeshGateTier.PC };
        public static string PackScenePathFor(MeshGateTier t) => AssetDir + "/ZombieCats_" + t switch
        {
            MeshGateTier.MobileLow => "Low", MeshGateTier.MobileMid => "Mid", MeshGateTier.MobileHigh => "High", _ => "PC",
        } + ".unity";
        public static string PackStreamingDir => Path.Combine(Application.dataPath, "StreamingAssets", "packs", PackName);

        /// <summary>Copy the pack: every GLB to StreamingAssets (runtime), diorama + cat GLB and the cat FBX to Assets (editor).</summary>
        public static bool CopyPack(string samplesDir)
        {
            var src = Path.Combine(samplesDir, "packs", PackName);
            if (!Directory.Exists(src)) return false;
            Directory.CreateDirectory(PackStreamingDir);
            Directory.CreateDirectory(Path.GetFullPath(PackAssetDir));
            foreach (var glb in Directory.GetFiles(src, "zc_*.glb"))
            {
                var name = Path.GetFileName(glb);
                if (name.Contains(".godot.")) continue;
                File.Copy(glb, Path.Combine(PackStreamingDir, name), true);
                if (name.StartsWith("zc_diorama") || name.StartsWith("zc_zombie_cat")) File.Copy(glb, Path.GetFullPath(PackAssetDir + "/" + name), true);
            }
            File.Copy(Path.Combine(src, "index.json"), Path.Combine(PackStreamingDir, "index.json"), true);
            var catFbx = Path.Combine(src, "zc_zombie_cat.fbx");
            if (File.Exists(catFbx)) File.Copy(catFbx, Path.GetFullPath(PackAssetDir + "/zc_zombie_cat.fbx"), true);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            ExtractFbxTextures(PackAssetDir + "/zc_zombie_cat.fbx", PackAssetDir + "/zc_zombie_cat_textures");
            SetupHumanoid(PackAssetDir + "/zc_zombie_cat.fbx");
            return true;
        }

        // --------------------------------------------------------------------------------------------
        // Generated pack: samples/packs/generated → StreamingAssets + GeneratedTiers.unity (every asset × every tier)
        // --------------------------------------------------------------------------------------------
        public static string TierShowcasePath => AssetDir + "/GeneratedTiers.unity";

        /// <summary>Copy the generated pack's GLBs and index.json to StreamingAssets/packs/generated.</summary>
        public static bool CopyGeneratedPack(string samplesDir)
        {
            var src = Path.Combine(samplesDir, "packs", "generated");
            if (!File.Exists(Path.Combine(src, "index.json"))) return false;
            var dst = Path.Combine(Application.dataPath, "StreamingAssets", "packs", "generated");
            Directory.CreateDirectory(dst);
            foreach (var f in Directory.GetFiles(src, "*.glb"))
                if (!Path.GetFileName(f).Contains(".godot.")) File.Copy(f, Path.Combine(dst, Path.GetFileName(f)), true);
            File.Copy(Path.Combine(src, "index.json"), Path.Combine(dst, "index.json"), true);
            AssetDatabase.Refresh(ImportAssetOptions.ForceSynchronousImport);
            return true;
        }

        /// <summary>GeneratedTiers.unity: a camera, a sun and a MeshGateTierShowcase — press Play to see every generated
        /// asset at mobile-low, mobile-mid, mobile-high and pc next to each other with their triangle counts.</summary>
        public static void BuildTierShowcaseScene()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.07f, 0.08f, 0.12f);
            cam.fieldOfView = 40f;
            camGo.transform.SetPositionAndRotation(new Vector3(-3.3f, 11f, 6f), Quaternion.Euler(55f, 180f, 0f));
            var sun = new GameObject("Sun").AddComponent<Light>();
            sun.type = LightType.Directional; sun.intensity = 1.3f; sun.shadows = LightShadows.Soft;
            sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.45f, 0.47f, 0.55f);
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);
            floor.name = "Floor"; floor.transform.position = new Vector3(-3.3f, -0.002f, -8f); floor.transform.localScale = new Vector3(4f, 1f, 4f);
            var mat = new Material(Shader.Find("Universal Render Pipeline/Lit") ?? Shader.Find("Standard")) { color = new Color(0.13f, 0.14f, 0.19f) };
            AssetDatabase.CreateAsset(mat, AssetDir + "/GeneratedTiersFloor.mat");
            floor.GetComponent<MeshRenderer>().sharedMaterial = mat;
            new GameObject("Tier showcase").AddComponent<MeshGateTierShowcase>();
            EditorSceneManager.SaveScene(scene, TierShowcasePath);
        }

        static GameObject Holder(string name, Vector3 pos, float yaw)
        {
            var h = new GameObject(name);
            h.transform.SetPositionAndRotation(pos, Quaternion.Euler(0f, yaw, 0f));
            return h;
        }

        static void AnimateWith(GameObject go, AnimationClip clip, string controllerPath)
        {
            if (!clip) return;
            if (!go.TryGetComponent<Animator>(out var animator)) animator = go.AddComponent<Animator>();
            animator.runtimeAnimatorController = UnityEditor.Animations.AnimatorController.CreateAnimatorControllerAtPathWithClip(controllerPath, clip);
        }

        /// <summary>Diorama (glTF editor import, visible without Play), a runtime zombie cat that shambles, the cat FBX as Humanoid,
        /// and — if the hero sample is imported — the hero playing the cat's Humanoid "shamble" (retargeting between characters).</summary>
        /// <summary>All three quality scenes (ZombieCats_Low / _Mid / _PC).</summary>
        public static void BuildPackScene()
        {
            foreach (var t in PackSceneTiers) BuildPackScene(t);
        }

        public static void BuildPackScene(MeshGateTier tier)
        {
            var id = MeshGateQuality.Id(tier);
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            new GameObject("MeshGate Quality (" + id + ")").AddComponent<MeshGateQuality>().tier = tier;
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = new Color(0.07f, 0.06f, 0.11f);
            cam.fieldOfView = 40f;
            var orbit = camGo.AddComponent<MeshGateOrbitCamera>();
            orbit.yaw = 215f; orbit.pitch = 32f;
            var lightGo = new GameObject("Moon Light");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional; light.intensity = 1.3f; light.shadows = LightShadows.Soft;
            light.color = new Color(0.85f, 0.9f, 1f);
            lightGo.transform.rotation = Quaternion.Euler(45f, 150f, 0f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.45f, 0.45f, 0.65f);
            RenderSettings.ambientEquatorColor = new Color(0.3f, 0.3f, 0.35f);
            RenderSettings.ambientGroundColor = new Color(0.12f, 0.12f, 0.15f);

            var dioFile = id == "pc" ? "zc_diorama.glb" : "zc_diorama." + id + ".glb";   // this tier's detail, visible without Play
            var dio = AssetDatabase.LoadAssetAtPath<GameObject>(PackAssetDir + "/" + dioFile);
            if (dio) ((GameObject)PrefabUtility.InstantiatePrefab(dio)).name = "Zombie Cats diorama (" + dioFile + ")";

            var runtimeCat = new GameObject("Zombie cat (runtime)");
            runtimeCat.transform.SetPositionAndRotation(new Vector3(-1.3f, 0f, 5.3f), Quaternion.identity);   // glTF +Z (Blender -Y) is the front
            var asset = runtimeCat.AddComponent<MeshGateAsset>();
            asset.source = "packs/" + PackName + "/zc_zombie_cat.glb";
            asset.playOnLoad = "shamble";
            runtimeCat.AddComponent<MeshGateInteraction>();

            var catFbxPath = PackAssetDir + "/zc_zombie_cat.fbx";
            var catFbx = AssetDatabase.LoadAssetAtPath<GameObject>(catFbxPath);
            var catClips = AssetDatabase.LoadAllAssetsAtPath(catFbxPath).OfType<AnimationClip>().Where(c => !c.name.StartsWith("__")).ToArray();
            var shamble = catClips.FirstOrDefault(c => c.name == "shamble");
            if (catFbx)
            {
                var h = Holder("Zombie cat (FBX Humanoid)", new Vector3(0f, 0f, 5.3f), 180f);   // Unity FBX import faces -Z
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(catFbx);
                inst.transform.SetParent(h.transform, false);
                AnimateWith(inst, catClips.FirstOrDefault(c => c.name == "idle"), PackAssetDir + "/ZombieCatIdle.controller");
            }
            var hero = AssetDatabase.LoadAssetAtPath<GameObject>(HeroFbxAssetPath);
            if (hero && shamble)
            {
                var h = Holder("Hero retargeted: cat's shamble (Humanoid)", new Vector3(1.4f, 0f, 5.3f), 180f);
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(hero);
                inst.transform.SetParent(h.transform, false);
                AnimateWith(inst, shamble, PackAssetDir + "/HeroShamble.controller");
            }
            new GameObject("MeshGate HUD").AddComponent<MeshGateHud>().hideFlags = HideFlags.None;
            // frame the whole street from the front-left
            orbit.pivot = new Vector3(0f, 0.6f, 1.2f);
            orbit.distance = 13.5f;
            EditorSceneManager.SaveScene(scene, PackScenePathFor(tier));
            Debug.Log("MeshGate: pack scene (" + id + ") saved → " + PackScenePathFor(tier));
        }

        /// <summary>The cat FBX is a valid Humanoid, the diorama imported with all its clips.</summary>
        public static string VerifyPack()
        {
            var catFbxPath = PackAssetDir + "/zc_zombie_cat.fbx";
            var importer = AssetImporter.GetAtPath(catFbxPath) as ModelImporter;
            if (importer == null) return "MeshGate: pack not copied — skipping";
            var avatar = AssetDatabase.LoadAllAssetsAtPath(catFbxPath).OfType<Avatar>().FirstOrDefault();
            if (avatar == null || !avatar.isValid || !avatar.isHuman)
                throw new System.Exception("MeshGate: zombie cat FBX did not produce a Humanoid avatar");
            var clips = importer.defaultClipAnimations.Select(c => c.name).OrderBy(n => n).ToArray();
            if (!clips.SequenceEqual(new[] { "idle", "shamble" })) throw new System.Exception("MeshGate: zombie cat clips " + string.Join(", ", clips));
            var dioClips = AssetDatabase.LoadAllAssetsAtPath(PackAssetDir + "/zc_diorama.glb").OfType<AnimationClip>().Select(c => c.name).OrderBy(n => n).ToArray();
            if (dioClips.Length != 5) throw new System.Exception("MeshGate: diorama clips " + string.Join(", ", dioClips));
            return $"MeshGate: pack — zombie cat Humanoid valid ({avatar.humanDescription.human.Length} bones mapped), clips {string.Join(", ", clips)}; diorama clips {string.Join(", ", dioClips)}";
        }

        /// <summary>Report on the editor import of GLB and FBX; throws if they diverge.</summary>
        public static string Verify()
        {
            var gltf = AssetDatabase.LoadAssetAtPath<GameObject>(GlbAssetPath);
            if (!gltf) throw new System.Exception("MeshGate: editor import of the GLB failed (is glTFast installed?)");
            var gltfNames = gltf.GetComponentsInChildren<Transform>(true).Select(t => t.name).Where(n => n != gltf.name).OrderBy(n => n).ToArray();
            var gltfClips = AssetDatabase.LoadAllAssetsAtPath(GlbAssetPath).OfType<AnimationClip>().Select(c => c.name).OrderBy(n => n).ToArray();
            var report = $"MeshGate: glTF import — {gltfNames.Length} nodes, clips: {string.Join(", ", gltfClips)}";
            foreach (var must in new[] { "crate_body", "crate_lid", "beacon_post", "beacon_ring", "handle_l" })
                if (!gltfNames.Contains(must)) throw new System.Exception("MeshGate: glTF import is missing node " + must);

            var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(FbxAssetPath);
            if (!fbx) return report + "\nMeshGate: FBX not found — export with the --fbx flag";
            var importer = (ModelImporter)AssetImporter.GetAtPath(FbxAssetPath);
            var clips = importer.defaultClipAnimations.Select(c => c.name).OrderBy(n => n).ToArray();
            var fbxNames = fbx.GetComponentsInChildren<Transform>(true).Select(t => t.name).Where(n => n != fbx.name).OrderBy(n => n).ToArray();
            var fbxBounds = RendererBounds(fbx); var gltfBounds = RendererBounds(gltf);
            var mats = fbx.GetComponentsInChildren<Renderer>(true).SelectMany(r => r.sharedMaterials).Where(m => m).Distinct().ToArray();
            var textured = mats.Count(m => m.mainTexture);
            report += $"\nMeshGate: FBX import — {fbxNames.Length} nodes, bounds {fbxBounds.size}, clips: {string.Join(", ", clips)}, materials: {string.Join(", ", mats.Select(m => m.name))} (textured: {textured}); File Scale {importer.fileScale}";
            if (!fbxNames.SequenceEqual(gltfNames))
                throw new System.Exception($"MeshGate: FBX and GLB hierarchies differ:\n FBX: {string.Join(", ", fbxNames)}\n GLB: {string.Join(", ", gltfNames)}");
            if ((fbxBounds.size - gltfBounds.size).magnitude > 0.02f)
                throw new System.Exception($"MeshGate: FBX bounds {fbxBounds.size} ≠ GLB {gltfBounds.size} — check export units/scale");
            if (!clips.SequenceEqual(gltfClips))
                throw new System.Exception($"MeshGate: FBX clips ({string.Join(", ", clips)}) ≠ GLB ({string.Join(", ", gltfClips)})");
            foreach (var t in fbx.GetComponentsInChildren<Transform>(true))
                if (Vector3.Distance(t.localScale, Vector3.one) > 1e-3f) throw new System.Exception($"MeshGate: FBX — scale ≠ 1 on {t.name} ({t.localScale})");
            if (textured < 1) throw new System.Exception("MeshGate: FBX — no material received an embedded texture");
            report += "\nMeshGate: FBX matches GLB in hierarchy, bounds, scale and clips";
            return report + "\n" + VerifyHero();
        }

        /// <summary>Character: the FBX yields a valid Humanoid avatar, the GLB a skin with the same bones and clips.</summary>
        public static string VerifyHero()
        {
            var fbx = AssetDatabase.LoadAssetAtPath<GameObject>(HeroFbxAssetPath);
            if (!fbx) return "MeshGate: character (meshgate_hero.fbx) not found — skipping";
            var importer = (ModelImporter)AssetImporter.GetAtPath(HeroFbxAssetPath);
            var avatar = AssetDatabase.LoadAllAssetsAtPath(HeroFbxAssetPath).OfType<Avatar>().FirstOrDefault();
            if (importer.animationType != ModelImporterAnimationType.Human || avatar == null || !avatar.isValid || !avatar.isHuman)
                throw new System.Exception($"MeshGate: character FBX did not produce a Humanoid avatar (type={importer.animationType}, avatar={(avatar ? $"valid={avatar.isValid} human={avatar.isHuman}" : "null")})");
            var mapped = avatar.humanDescription.human.Length;
            var clips = importer.defaultClipAnimations.Select(c => c.name).OrderBy(n => n).ToArray();
            var smr = fbx.GetComponentInChildren<SkinnedMeshRenderer>(true);
            if (!smr) throw new System.Exception("MeshGate: character FBX has no SkinnedMeshRenderer");
            var uv = smr.sharedMesh.uv != null && smr.sharedMesh.uv.Length == smr.sharedMesh.vertexCount;
            var glb = AssetDatabase.LoadAssetAtPath<GameObject>(HeroGlbAssetPath);
            var glbSmr = glb ? glb.GetComponentInChildren<SkinnedMeshRenderer>(true) : null;
            var report = $"MeshGate: character — Humanoid avatar valid, {mapped} bones mapped, {smr.bones.Length} bones in skin, UV {(uv ? "present" : "MISSING")}, FBX clips: {string.Join(", ", clips)}"
                       + (glbSmr ? $"; glTF skin: {glbSmr.bones.Length} bones" : "; glTF import of the character not found");
            if (!uv) throw new System.Exception("MeshGate: character has no UVs");
            if (mapped < 15) throw new System.Exception($"MeshGate: Humanoid mapped only {mapped} bones");
            if (glbSmr && glbSmr.bones.Length != smr.bones.Length) throw new System.Exception($"MeshGate: FBX skin bone count ({smr.bones.Length}) ≠ glTF ({glbSmr.bones.Length})");
            return report;
        }

        static Bounds RendererBounds(GameObject go)
        {
            var rs = go.GetComponentsInChildren<Renderer>(true);
            var b = rs.Length > 0 ? rs[0].bounds : new Bounds();
            foreach (var r in rs) b.Encapsulate(r.bounds);
            return b;
        }
    }
}
