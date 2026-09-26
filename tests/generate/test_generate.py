#!/usr/bin/env python3
"""Generation without Blender or an AI: safety rules, prompt, code extraction, names. Pure stdlib.

    python3 tests/generate/test_generate.py
"""

import re
import sys
from pathlib import Path
for _s in (sys.stdout, sys.stderr):   # Windows consoles default to cp1252; the checks print ✓ and ✗
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "sources" / "generate"))
import generate  # noqa: E402
import safety  # noqa: E402

FAILS = []


def step(name, ok, detail=""):
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)


# examples shipped with the repository are allowed
for ex in sorted((ROOT / "sources" / "generate" / "examples").glob("*.py")):
    step(f"example {ex.name} passes safety", not safety.check(ex.read_text()), str(safety.check(ex.read_text())))

OK = "def build(mg):\n    mg.part('cube', '#ffffff')\n"
DENIED = {
    "import os": "import os\n" + OK,
    "from subprocess": "from subprocess import run\n" + OK,
    "bpy": OK + "    bpy.ops.wm.quit_blender()\n",
    "open()": OK + "    open('/tmp/x', 'w').write('x')\n",
    "eval": OK + "    eval('1+1')\n",
    "__import__": OK + "    __import__('os')\n",
    "dunder attribute": OK + "    x = mg.__class__\n",
    "private kit member": OK + "    mg._mat.name = 'x'\n",
    "image.save_render": OK + "    img.save_render('/tmp/x.png')\n",
    "filepath": OK + "    img.filepath_raw = '/tmp/x'\n",
    "driver_add": OK + "    obj.driver_add('location')\n",
    "getattr": OK + "    getattr(mg, 'part')\n",
    "class": "class A:\n    pass\n" + OK,
    "with": OK + "    with x:\n        pass\n",
    "missing build": "def make(mg):\n    pass\n",
    "build with two args": "def build(mg, x):\n    pass\n",
    "syntax error": "def build(mg)\n    pass\n",
    "dunder format": OK + "    s = '{0.__class__}'.format(mg)\n",
}
for label, code in DENIED.items():
    step(f"safety rejects {label}", bool(safety.check(code)))
step("safety allows math/random/mathutils imports",
     not safety.check("import math\nimport random\nfrom mathutils import Vector\n" + OK))
step("safety allows a bare _ as a throwaway name", not safety.check("def build(mg):\n    for _ in range(3):\n        pass\n"))
step("finish follows the style: lowpoly → faceted, realistic → weathered, vertex colours → no bake",
     generate.resolve_finish("auto", "lowpoly", "texture") == "faceted"
     and generate.resolve_finish("auto", "realistic", "texture") == "weathered"
     and generate.resolve_finish("auto", "realistic", "vertex") == "none"
     and generate.resolve_finish("auto", "stylized", "texture") == "none"
     and generate.resolve_finish("faceted", "stylized", "texture") == "faceted")
_w = generate.build_prompt("a crate", name="crate", style="realistic", size=0.5, tiers=["pc"], finish="weathered")
step("the prompt tells the AI that weathering is baked on top", "do not model dirt" in _w)
step("--pbr bakes a clean full PBR set for flat styles, never with vertex colours",
     generate.resolve_finish("auto", "stylized", "texture", True) == "clean"
     and generate.resolve_finish("auto", "realistic", "texture", True) == "weathered"
     and generate.resolve_finish("auto", "stylized", "vertex", True) == "none"
     and generate.TEXTURES["8k"] == 8192)
_a = generate.parse_anims("open: the lid opens; idle: the lamp sways\nкрутятся лопасти")
step("animation requests become named clips", _a == [("open", "the lid opens"), ("idle", "the lamp sways"), ("clip_3", "крутятся лопасти")])
step("the prompt lists the requested clips", "| `open` | the lid opens |" in generate.build_prompt(
    "a chest", name="chest", style="stylized", size=0.5, tiers=["pc"], anims=_a))
step("missing clips are found in the report", generate.missing_clips(
    {"canonical": "pc", "tiers": {"pc": {"clips": ["open"]}}}, _a) == ["idle", "clip_3"])

# restricted globals: the guarded __import__ hands out only allowed modules
import math  # noqa: E402
g = safety.restricted_globals({"math": math, "random": __import__("random"), "mathutils": math})
try:
    exec("import os", g)
    step("runtime import guard blocks os", False)
except ImportError:
    step("runtime import guard blocks os", True)
exec("import math as m\nx = m.pi", g)
step("runtime import guard allows math", abs(g["x"] - math.pi) < 1e-9)
step("restricted builtins have no open/eval", "open" not in g["__builtins__"] and "eval" not in g["__builtins__"])

# prompt
prompt = generate.build_prompt("a wooden crate", name="crate", style="stylized", size=0.6, tiers=["mobile-low", "pc"])
step("prompt carries the description, size and tiers", "a wooden crate" in prompt and "about 0.6 m" in prompt
     and "| mobile-low | 8,000 |" in prompt and "mobile-mid (not built)" in prompt)
step("prompt lists every public kit method", all(f"mg.{m}(" in prompt for m in (
    "part", "lathe", "tube", "extrude", "mirror_x", "copy", "join", "pivot", "attach", "group", "animate", "color",
    "seg", "at_least", "blob", "skin", "cut", "bend", "twist", "sculpt"))) and "mg._" not in prompt
step("prompt has no unfilled placeholders",   # dict literals in the kit docs are fine; {name} fields are not
     not re.search(r"\{[a-z_]+\}", prompt.split("# Example")[0].replace("{prompt_file}", "")))
fb = generate.feedback_block("def build(mg):\n    pass\n", ["tier pc: boom"], ["detail: more"])
step("feedback block quotes code and problems", "tier pc: boom" in fb and "def build(mg)" in fb)

# answer parsing and names
ans = "Here you go:\n```python\nimport math\n\ndef build(mg):\n    pass\n```\nEnjoy!"
step("extract_code takes the python block", generate.extract_code(ans).startswith("import math"))
step("extract_code without fences keeps the text", "def build" in generate.extract_code("def build(mg):\n    pass"))
step("slug transliterates Russian", generate.slug("Ржавый пожарный гидрант") == "rzhavyy_pozharnyy_gidrant",
     generate.slug("Ржавый пожарный гидрант"))
step("slug drops stop words", generate.slug("A lamp with a shade") == "lamp_shade", generate.slug("A lamp with a shade"))

# reference pictures: the prompt gains a section, the CLI gets the file
import tempfile  # noqa: E402
ref_prompt = generate.build_prompt("", name="can", style="stylized", size=0, tiers=["pc"], reference="reference.png")
step("prompt with a picture names the file and the rules", "`reference.png`" in ref_prompt and "first decide what the object is" in ref_prompt)
tmpdir = Path(tempfile.mkdtemp(prefix="meshgate-ai-test-"))
seer = tmpdir / "seer.py"
seer.write_text("import os, sys\nprompt = sys.stdin.read()\nimg = sys.argv[1]\n"
                "print('```python\\n# sees', os.path.basename(img), os.path.getsize(img) > 1000, 'Reference image' in prompt,"
                " '\\ndef build(mg):\\n    pass\\n```')\n")
picture = ROOT / "sources" / "generate" / "examples" / "hydrant_picture.png"
answer = generate.ask_ai("claude", "make it", ai_cmd=f"{sys.executable} {seer} {{image}}", image=str(picture))
step("custom CLI receives the picture as reference.png in its folder", "sees reference.png True" in answer, answer[:120])
blind = tmpdir / "blind.py"
blind.write_text("import sys\nprompt = sys.stdin.read()\n"
                 "print('```python\\n# path in prompt:', 'Reference image: ' in prompt and 'reference.png' in prompt,"
                 " '\\ndef build(mg):\\n    pass\\n```')\n")
answer = generate.ask_ai("claude", "make it", ai_cmd=f"{sys.executable} {blind}", image=str(picture))
step("a CLI without {image} gets the path in the prompt", "path in prompt: True" in answer, answer[:120])

# adapter argument shapes, without running any real CLI
import subprocess as _sp  # noqa: E402
captured = {}


class _Done:
    returncode, stdout, stderr = 0, "```python\ndef build(mg):\n    pass\n```", ""


def fake_run(cmd, **kw):
    captured["cmd"], captured["cwd"] = cmd, kw.get("cwd")
    captured["files"] = sorted(p.name for p in Path(kw["cwd"]).iterdir())
    return _Done()


real_run, real_which = generate.procs.run, generate.shutil.which
generate.procs.run, generate.shutil.which = fake_run, (lambda exe: f"/usr/bin/{exe}")
try:
    generate.ask_ai("claude", "make it", image=str(picture))
    c = captured["cmd"]
    step("claude + picture: only the Read tool, allowed, image-aware system prompt",
         c[c.index("--tools") + 1] == "Read" and c[c.index("--allowedTools") + 1] == "Read"
         and "reference image" in c[c.index("--system-prompt") + 1] and captured["files"] == ["reference.png"], str(c))
    generate.ask_ai("claude", "make it")
    c = captured["cmd"]
    step("claude without a picture: no tools at all", c[c.index("--tools") + 1] == "" and "--allowedTools" not in c)
    generate.ask_ai("codex", "make it", image=str(picture))
    step("codex + picture: -i <reference>", "-i" in captured["cmd"] and captured["cmd"][captured["cmd"].index("-i") + 1].endswith("reference.png"))
    generate.ask_ai("gemini", "make it", image=str(picture))
    c = captured["cmd"]
    step("gemini + picture: @reference.png in -p", "@reference.png" in c[c.index("-p") + 1])
finally:
    generate.procs.run, generate.shutil.which = real_run, real_which
import mesh  # noqa: E402
step("mesh providers are registered", set(mesh.PROVIDERS) == {"triposr", "meshy", "tripo", "fal", "command"})
step("TripoSR decodes sRGB vertex colours", mesh.PROVIDERS["triposr"].INFO.get("vertex_srgb") is True)
step("default provider without a picture never picks an image-only one without text → image",
     mesh.default_provider(False) != "triposr" or any(mesh.images.available().values()))

step("relative paths in a custom command become absolute (it runs in an empty folder)",
     generate.absolute_paths(["python3", "tests/generate/fake_ai.py", "--x", "{image}"])[1] == str((ROOT / "tests/generate/fake_ai.py").resolve())
     if Path.cwd() == ROOT else True)
# own triangle limits
step("--tris 800 caps every built tier", generate.parse_caps("800", ["mobile-low", "pc"]) == {"mobile-low": 800, "pc": 800})
step("--tris low=150,pc=2000 uses tier aliases", generate.parse_caps("low=150,pc=2000", generate.ORDER) == {"mobile-low": 150, "pc": 2000})
for bad in ("low=5", "tiny=100", "low=abc", "low"):
    try:
        generate.parse_caps(bad, generate.ORDER)
        step(f"--tris {bad} is refused", False)
    except ValueError:
        step(f"--tris {bad} is refused", True)
capped = generate.build_prompt("a crate", name="crate", style="lowpoly", size=0, tiers=["mobile-low", "pc"], caps={"mobile-low": 100, "pc": 600})
step("the prompt shows your limits and asks to stay under them", "YOUR LIMIT" in capped and "| 600 |" in capped and "Stay under" in capped)
# Codex draws concept pictures (stand-in CLI): a turnaround sheet prompt, out.png picked up from its work folder
import os  # noqa: E402
import stat as _stat  # noqa: E402
shim_dir = Path(tempfile.mkdtemp(prefix="meshgate-codex-shim-"))
shim = shim_dir / ("codex.cmd" if os.name == "nt" else "codex")
if os.name == "nt":
    shim.write_text(f'@"{sys.executable}" "{ROOT / "tests" / "generate" / "fake_codex.py"}" %*\n')
else:
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{ROOT / "tests" / "generate" / "fake_codex.py"}" "$@"\n')
    shim.chmod(shim.stat().st_mode | _stat.S_IEXEC)
os.environ["MESHGATE_CODEX"] = str(shim)
drawn = mesh.images.text_to_image("a cast-iron street lamp", tmpdir / "concept.png", "codex", log=lambda *_: None, kind="sheet")
step("codex draws a concept picture and MeshGate picks up out.png", drawn.exists() and drawn.read_bytes()[:4] == b"\x89PNG")
sheet_prompt = mesh.images.concept_prompt("a lamp", "sheet")
step("the sheet prompt asks for front/side/back/top at one scale, front to the right / bottom",
     all(w in sheet_prompt for w in ("FRONT", "SIDE", "BACK", "TOP", "SAME scale", "RIGHT edge", "BOTTOM edge")))
step("the single-view prompt asks for a whole, centred 3/4 view on a plain background",
     all(w in mesh.images.concept_prompt("a lamp", "single") for w in ("Three-quarter", "centred", "Plain light-grey")))
sheet_model = generate.build_prompt("a lamp", name="lamp", style="stylized", size=0, tiers=["pc"], reference="reference.png",
                                    reference_kind="sheet")
step("the model prompt explains how to read each view and its axes",
     "turnaround sheet" in sheet_model and "SIDE: horizontal = Y" in sheet_model and "TOP: horizontal = X" in sheet_model)
os.environ.pop("MESHGATE_CODEX")
print("Result: " + ("generation checks passed." if not FAILS else f"{len(FAILS)} failed."))
sys.exit(1 if FAILS else 0)
