#!/usr/bin/env python3
"""MeshGate generation — a text description in, a game-ready asset per quality tier out, through any AI CLI.

    python3 meshgate.py gen "a cast-iron fire hydrant" [--name fire_hydrant] [--style stylized] [--size 0.8]
                        [--tiers mobile-low,mobile-mid,mobile-high,pc] [--ai claude|codex|gemini|ollama] [--model M]
                        [--ai-cmd "llm -m gpt-4o"] [--attempts 3] [--collision none|box|convex] [--out-dir out/gen/NAME]
    python3 meshgate.py gen --code my_model.py --name my_model        # run your own build(mg), no AI
    python3 meshgate.py gen "..." --prompt-only                         # print the prompt and stop
    python3 meshgate.py gen --list-ai                                   # which AI CLIs are installed

How it works: the prompt carries the description, the quality tiers from core/profiles.json and the modeling kit's
API (read from its docstrings). The AI answers with one `build(mg)` function; MeshGate checks it (safety.py), runs it in
Blender once per tier (run_generated.py), validates every file and, if something is wrong — an exception, a budget,
a contract warning, the wrong size — sends the problems back and asks for a corrected version, up to --attempts times.

--events prints one JSON object per line (stage, attempt, report) for the desktop app. Pure stdlib.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import keys  # noqa: E402  saved API keys (~/.meshgate/keys.json) — the environment still wins
keys.apply_env()
import mesh  # noqa: E402  neural mesh providers (image → 3D, text → 3D)
import procs  # noqa: E402  child processes stop with the run
import safety  # noqa: E402

MODELING = ROOT / "sources" / "blender" / "meshgate_blender" / "modeling.py"
PROFILES = ROOT / "core" / "profiles.json"
PROMPT = HERE / "prompts" / "model.md"
EXAMPLE = HERE / "examples" / "treasure_chest.py"
RUNNER = HERE / "run_generated.py"
REFINE = HERE / "refine.py"
ORDER = ["mobile-low", "mobile-mid", "mobile-high", "pc"]

STYLES = {
    "stylized": "stylized game art: clean readable shapes, slightly exaggerated proportions, soft bevels, a limited "
                "harmonious palette (think Fortnite or Overwatch props)",
    "lowpoly": "low-poly: faceted flat-shaded shapes (smooth=False), few segments even on rich tiers, bold flat colours",
    "realistic": "realistic: true-to-life proportions and silhouette, physically plausible materials (real metal, wood, "
                 "paint values), natural colour variation, bevelled edges, believable wear details on rich tiers; "
                 "an ordinary object, never a cartoon mascot",
    "toon": "cartoon / chibi: rounded chunky shapes, big simple forms, saturated colours",
}

# Finishes the kit applies after the build, and what the AI is told about them
FINISHES = {"lowpoly": "faceted", "realistic": "weathered"}
FINISH_NOTES = {
    "faceted": ". MeshGate renders it faceted: flat shading and few segments are enforced, so build bold, simple, chunky "
               "forms and let the facets show",
    "weathered": ". MeshGate bakes weathering on top: dirt in crevices and near the ground, colour variation, fine "
                 "surface relief and the look of each material. Name every colour by what it is made of (wood_dark, "
                 "cardboard, stone, iron, rust, rope, fabric, grass, bone) or pass material=, and give it its clean "
                 "base colour; do not model dirt, stains, grain or noise yourself",
}


ANIM_BLOCK = """
# Animations requested

Make exactly these clips with `mg.animate`, named as given. Parts that move must be separate meshes: `mg.pivot` them
to their hinge or axle and `mg.attach` them to the body (rule 4). Keep each clip 1–4 s at 30 fps and make loops end
where they start.

| clip name | what happens |
|---|---|
{rows}
"""


def parse_anims(text: str | None) -> list[tuple[str, str]]:
    """'open: the lid opens; idle: the lamp sways' (lines or ;) → [(clip name, what happens)]. Without a name, the
    first English words become it (open_lid), else clip_1, clip_2…"""
    out: list[tuple[str, str]] = []
    for item in re.split(r"[;\n]+", text or ""):
        item = item.strip(" -•\t")
        if not item:
            continue
        name, _, what = item.partition(":") if re.match(r"^[A-Za-z][\w -]{0,30}:", item) else ("", "", item)
        slug = re.sub(r"[^a-z0-9]+", "_", (name or " ".join(re.findall(r"[A-Za-z]+", what)[:2])).lower()).strip("_")
        slug = slug or f"clip_{len(out) + 1}"
        while slug in {n for n, _ in out}:
            slug += "_2"
        out.append((slug[:32], (what or item).strip()))
    return out[:8]


def resolve_finish(finish: str, style: str, colors: str) -> str:
    """auto → the style's finish (low-poly: faceted, realistic: weathered). Weathering bakes textures, so it needs
    texture colours; with vertex colours it falls back to none."""
    f = FINISHES.get(style, "none") if finish == "auto" else finish
    return "none" if f == "weathered" and colors == "vertex" else f


SYSTEM = ("You write Python build code for the MeshGate modeling kit. Reply with exactly one ```python code block "
          "that defines build(mg). Do not use tools, do not ask questions.")
SYSTEM_IMAGE = ("You write Python build code for the MeshGate modeling kit. First look at the reference image file named "
                "in the prompt (Read tool, that file only), then reply with exactly one ```python code block that "
                "defines build(mg). Do not use any other tool, do not ask questions.")

# AI command-line tools. The prompt goes to stdin; the answer is read from stdout (or a file for codex).
ADAPTERS = {
    "claude": {"exe": "claude", "args": ["-p", "--output-format", "text", "--tools", "", "--no-session-persistence",
                                         "--strict-mcp-config", "--disable-slash-commands", "--system-prompt", SYSTEM],
               "model": ["--model"], "url": "https://docs.claude.com/en/docs/claude-code"},
    "codex": {"exe": "codex", "args": ["exec", "--skip-git-repo-check", "--sandbox", "read-only", "--color", "never"],
              "model": ["-m"], "last_message": "--output-last-message", "stdin_arg": "-",
              "url": "https://github.com/openai/codex"},
    "gemini": {"exe": "gemini", "args": ["-p", "Follow the instructions given on stdin exactly."], "model": ["-m"],
               "url": "https://github.com/google-gemini/gemini-cli"},
    "ollama": {"exe": "ollama", "args": ["run"], "model": [], "default_model": "qwen2.5-coder:14b",
               "url": "https://ollama.com"},
}

# One-click helpers for Studio: fixed commands only (never user text), run in a visible terminal window.
SETUP = {
    "claude": {"install": "npm install -g @anthropic-ai/claude-code", "login": "claude auth login"},
    "codex": {"install": "npm install -g @openai/codex", "login": "codex login"},
    "gemini": {"install": "npm install -g @google/gemini-cli", "login": "gemini"},
    "ollama": {"install": None, "login": "ollama pull qwen2.5-coder:14b",
               "download": "https://ollama.com/download"},
}

LOGIN_HINTS = {
    "claude": "sign in once in a terminal: run `claude` and type /login (or set ANTHROPIC_API_KEY)",
    "codex": "sign in once: `codex login` (or set OPENAI_API_KEY)",
    "gemini": "sign in once: run `gemini` and choose a login method (or set GEMINI_API_KEY)",
    "ollama": "start the server (`ollama serve`) and pull the model (`ollama pull qwen2.5-coder:14b`)",
}

_TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                     ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                      "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))
_STOP = {"a", "an", "the", "of", "with", "and", "for", "in", "on", "to", "s", "so"}


# ----------------------------------------------------------------------------
# prompt
# ----------------------------------------------------------------------------

def slug(text: str, words: int = 3) -> str:
    """ASCII asset name from a description in any language ('Ржавый пожарный гидрант' → 'rzhavyy_pozharnyy_gidrant')."""
    out = "".join(_TRANSLIT.get(c, c) for c in text.lower())
    parts = [w for w in re.split(r"[^a-z0-9]+", out) if w and w not in _STOP]
    return "_".join(parts[:words]) or "asset"


def api_reference() -> str:
    """mg.<method>(args) + docstring for every public Kit method, read from modeling.py without importing bpy."""
    tree = ast.parse(MODELING.read_text(encoding="utf-8"))
    kit = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Kit")
    lines = ["Attributes: `mg.tier` (current tier name), `mg.level` (0 = mobile-low … 3 = pc), `mg.rng` "
             "(random.Random, seeded — use it instead of random for repeatable results).", ""]
    for fn in kit.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name.startswith("_"):
            continue
        args = ast.unparse(fn.args).replace("self, ", "").replace("self", "")
        doc = ast.get_docstring(fn) or ""
        doc = " ".join(doc.split())
        lines.append(f"- `mg.{fn.name}({args})` — {doc}")
    return "\n".join(lines)


def tiers_table(profiles: dict, built: list[str], caps: dict | None = None) -> str:
    caps = caps or {}
    if caps:
        rows = ["| tier | tier budget | YOUR LIMIT — stay under it | for |", "|---|---|---|---|"]
    else:
        rows = ["| tier | max triangles | for |", "|---|---|---|"]
    for t in ORDER:
        p = profiles["profiles"][t]
        mark = "" if t in built else " (not built)"
        if caps:
            rows.append(f"| {t}{mark} | {p['asset']['max_tris']:,} | {caps[t]:,} |" if t in caps else
                        f"| {t}{mark} | {p['asset']['max_tris']:,} | — |")
            rows[-1] += f" {p['devices']} |"
        else:
            rows.append(f"| {t}{mark} | {p['asset']['max_tris']:,} | {p['devices']} |")
    if caps:
        rows.append("\nThe user set their own triangle limits. Stay under YOUR LIMIT on every tier: simplify the silhouette, "
                    "use fewer segments (vertices=6–8 with exact=True, lathe with few profile points) and drop small details "
                    "rather than exceeding it. MeshGate decimates anything above the limit, which looks worse.")
    return "\n".join(rows)


CAP_ALIASES = {"low": "mobile-low", "mid": "mobile-mid", "high": "mobile-high", "pc": "pc",
               "mobile-low": "mobile-low", "mobile-mid": "mobile-mid", "mobile-high": "mobile-high"}


def parse_caps(text: str | None, tiers: list[str]) -> dict:
    """--tris 800 → every built tier ≤ 800; --tris low=150,mid=400,pc=2000 → per tier (aliases low/mid/high/pc)."""
    if not text:
        return {}
    text = text.strip()
    if text.isdigit():
        caps = {t: int(text) for t in tiers}
    else:
        caps = {}
        for item in text.split(","):
            if "=" not in item:
                raise ValueError(f"--tris: '{item}' — use a number or tier=number, e.g. low=150,pc=2000")
            k, v = (x.strip() for x in item.split("=", 1))
            if k not in CAP_ALIASES or not v.isdigit():
                raise ValueError(f"--tris: '{item}' — tiers are low, mid, high, pc")
            caps[CAP_ALIASES[k]] = int(v)
    for t, v in caps.items():
        if v < 12:
            raise ValueError(f"--tris: {t}={v} is below 12 triangles")
    return caps


REFERENCE = ("\n# Reference image\n\nA picture of the object is attached as `{file}`{how}. Match its silhouette, proportions, "
             "parts and colours; ignore the background and the camera angle. Where the picture and the description "
             "disagree, follow the description. If there is no description, first decide what the object is and name it in "
             "a comment on the first line of your code, then size it like the real thing. Parts that look lit from "
             "within (lamps, screens, toxic goo that reads as glowing) get glow; everything else does not.\n")


REFERENCE_SHEET = ("\n# Reference: turnaround sheet\n\n`{file}` in the working folder is an orthographic turnaround sheet of the "
                   "object: FRONT (top-left), SIDE (top-right — the object's right side, its front pointing to the right "
                   "edge), BACK (bottom-left) and TOP (bottom-right — looking down, the front pointing to the bottom edge). "
                   "All four views share one scale. Read it like a modeler:\n"
                   "- FRONT: horizontal = X (the viewer's right is +X), vertical = Z. Take widths and heights here.\n"
                   "- SIDE: horizontal = Y with the front (-Y) on the right, vertical = Z. Take depths here.\n"
                   "- TOP: horizontal = X, vertical = Y with the front (-Y) at the bottom. Take the footprint and where "
                   "parts sit.\n"
                   "- Measure every part against the overall height and place it where the views agree; ignore the labels, "
                   "divider lines and grey background. Where the sheet and the description disagree, follow the "
                   "description.\n")


def build_prompt(description: str, *, name: str, style: str, size: float, tiers: list[str], feedback: str = "",
                 reference: str | None = None, caps: dict | None = None, reference_kind: str = "picture",
                 finish: str = "none", anims: list | None = None) -> str:
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))
    example = EXAMPLE.read_text(encoding="utf-8").strip()
    return PROMPT.read_text(encoding="utf-8").format(
        description=description.strip(), name=name, style=STYLES.get(style, style) + FINISH_NOTES.get(finish, ""),
        size=f"about {size:g} m in its largest dimension" if size else "use the real-world size of the object",
        tiers=tiers_table(profiles, tiers, caps), built=", ".join(tiers), api=api_reference(), example=example,
        feedback=feedback) + ((REFERENCE_SHEET.format(file=reference) if reference_kind == "sheet"
                                else REFERENCE.format(file=reference, how=" in the working folder")) if reference else "") \
        + (ANIM_BLOCK.format(rows="\n".join(f"| `{n}` | {w.replace('|', '/')} |" for n, w in anims)) if anims else "")


def missing_clips(report: dict, anims: list) -> list[str]:
    """Requested clip names the canonical tier does not have."""
    if not anims or not report.get("tiers"):
        return []
    canon = report["tiers"].get(report.get("canonical") or "", {}) or next(iter(report["tiers"].values()), {})
    have = set(canon.get("clips") or [])
    return [n for n, _ in anims if n not in have]


def feedback_block(code: str, problems: list[str], advice: list[str]) -> str:
    items = "\n".join(f"- {p}" for p in problems + advice)
    return (f"\n# Your previous attempt\n\n```python\n{code.strip()}\n```\n\nMeshGate built it and found these problems:\n\n"
            f"{items}\n\nReturn the complete corrected code (the whole build function, not a diff).\n")


def extract_code(text: str) -> str:
    """The first ```python block of an answer (or the longest fenced block, or the whole text if it has build())."""
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, flags=re.S)
    with_build = [b for b in blocks if "def build" in b]
    if with_build:
        return with_build[0].strip() + "\n"
    if blocks:
        return max(blocks, key=len).strip() + "\n"
    return text.strip() + "\n"


# ----------------------------------------------------------------------------
# AI CLIs
# ----------------------------------------------------------------------------

def available_ai() -> dict[str, str | None]:
    return {k: shutil.which(v["exe"]) for k, v in ADAPTERS.items()}


def signed_in(ai: str) -> bool | None:
    """True/False when the CLI can tell without spending a request (Claude Code: `claude auth status`), else None."""
    if ai == "claude":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return True
        exe = shutil.which("claude")
        if not exe:
            return None
        try:
            out = subprocess.run([exe, "auth", "status", "--json"], capture_output=True, text=True, timeout=20).stdout
            return bool(json.loads(out).get("loggedIn"))
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None
    return None


def absolute_paths(parts: list[str]) -> list[str]:
    """Custom commands run in an empty temporary folder: turn arguments that name existing files relative to where
    MeshGate was started (tests/fake_ai.py, ./my_cli) into absolute paths first."""
    out = []
    for c in parts:
        looks_like_path = ("/" in c or "\\" in c or c.startswith(".")) and not c.startswith("-") and "{" not in c
        out.append(str(Path(c).resolve()) if looks_like_path and Path(c).exists() else c)
    return out


def reference_name(image: str | None) -> str | None:
    return f"reference{Path(image).suffix.lower() or '.png'}" if image else None


def ask_ai(ai: str, prompt: str, *, model: str | None = None, ai_cmd: str | None = None, timeout: int = 900,
           image: str | None = None) -> str:
    """Send the prompt to an AI CLI and return its text answer. Runs in an empty temp folder so the CLI does not pick
    up project files or instructions. With `image`, the picture is copied there as reference.<ext> and handed to the
    CLI its own way (Claude Code: the Read tool for that folder only; Codex: -i; Gemini: @file; Ollama: the path)."""
    with tempfile.TemporaryDirectory(prefix="meshgate-ai-") as tmp:
        out_file = None
        ref = None
        if image:
            ref = os.path.join(tmp, reference_name(image))
            shutil.copyfile(image, ref)
        if ai_cmd:
            cmd = absolute_paths(shlex.split(ai_cmd, posix=os.name != "nt"))
            if any("{prompt_file}" in c for c in cmd):
                pf = os.path.join(tmp, "prompt.md")
                Path(pf).write_text(prompt, encoding="utf-8")
                cmd = [c.replace("{prompt_file}", pf) for c in cmd]
            if ref and not any("{image}" in c for c in cmd):
                prompt = f"{prompt}\n\nReference image: {ref}"
            cmd = [c.replace("{image}", ref or "") for c in cmd]
        else:
            spec = ADAPTERS[ai]
            exe = shutil.which(spec["exe"])
            if not exe:
                raise RuntimeError(f"{spec['exe']} is not installed — see {spec['url']} (or use --ai-cmd)")
            args = list(spec["args"])
            if ref and ai == "claude":
                i = args.index("--tools")
                args[i + 1] = "Read"
                args += ["--allowedTools", "Read"]
                args[args.index("--system-prompt") + 1] = SYSTEM_IMAGE
            elif ref and ai == "codex":
                args += ["-i", ref]
            elif ref and ai == "gemini":
                args[args.index("-p") + 1] += f" The reference image is @{os.path.basename(ref)}"
            elif ref and ai == "ollama":
                prompt = f"{prompt}\n\nReference image: {ref}"
            cmd = [exe] + args
            model = model or spec.get("default_model")
            if model:
                cmd += spec["model"] + [model]
            if spec.get("last_message"):
                out_file = os.path.join(tmp, "answer.txt")
                cmd += [spec["last_message"], out_file]
            if spec.get("stdin_arg"):
                cmd.append(spec["stdin_arg"])
        try:
            proc = procs.run(cmd, input=prompt, cwd=tmp, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"the AI CLI did not answer within {timeout} s") from None
        answer = Path(out_file).read_text(encoding="utf-8") if out_file and os.path.exists(out_file) else proc.stdout
        if proc.returncode != 0 and not answer.strip():
            raise RuntimeError(f"the AI CLI failed (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[-800:]}")
        if "def build" not in answer:   # "Not logged in", a refusal, a quota message — not worth another attempt
            text = " ".join((answer or proc.stderr).split())[:400]
            hint = LOGIN_HINTS.get(ai, "") if not ai_cmd else ""
            raise RuntimeError(f"the AI CLI answered without build code: \"{text}\"" + (f" — {hint}" if hint else ""))
        return answer


# ----------------------------------------------------------------------------
# Blender
# ----------------------------------------------------------------------------

def find_blender() -> str | None:
    sys.path.insert(0, str(ROOT))
    try:
        import meshgate  # the CLI next to the repository root
        return meshgate.find_blender()
    except Exception:  # noqa: BLE001
        return os.environ.get("MESHGATE_BLENDER") or shutil.which("blender")


PROGRESS = re.compile(r"^\s+(✓|✗|source:|·)")   # tier results, the source summary and notes from the runners


def run_blender(cmd: list[str], *, timeout: int, on_line=None) -> tuple[dict, str]:
    """Run a MeshGate Blender script, forward progress lines as they come, return (report, log). The process gets its
    own group, so a timeout (or a cancelled Studio job) stops Blender and anything it started."""
    import threading
    proc = procs.popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                       errors="replace", bufsize=1)
    lines: list[str] = []

    def pump():
        for line in proc.stdout:
            lines.append(line)
            if on_line and PROGRESS.match(line):
                on_line(line.rstrip())
    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        procs.stop_tree(proc)
        reader.join(2)
        return ({"ok": False, "problems": [f"Blender did not finish within {timeout} s — is there an endless loop, or far "
                                           f"too much geometry?"], "advice": []}, "".join(lines))
    reader.join(5)
    procs.ACTIVE.discard(proc)
    log = "".join(lines)
    m = re.search(r"MESHGATE_REPORT (.+)", log)
    if not m or not os.path.exists(m.group(1).strip()):
        tail = "\n".join(log.strip().splitlines()[-15:])
        return {"ok": False, "problems": [f"Blender stopped without a report:\n{tail}"], "advice": []}, log
    return json.loads(Path(m.group(1).strip()).read_text(encoding="utf-8")), log


def run_in_blender(blender: str, code_path: Path, *, name: str, out_dir: Path, tiers: list[str], targets: str,
                   collision: str, size: float, preview: bool, seed: int, timeout: int = 600,
                   on_line=None, colors: str = "texture", caps: dict | None = None, finish: str = "none") -> tuple[dict, str]:
    cmd = [blender, "-b", "--factory-startup", "--disable-autoexec", "-P", str(RUNNER), "--", "--finish", finish,
           "--code", str(code_path), "--name", name, "--out-dir", str(out_dir), "--tiers", ",".join(tiers),
           "--targets", targets, "--collision", collision, "--size", str(size or 0), "--seed", str(seed),
           "--colors", colors, "--caps", ",".join(f"{k}={v}" for k, v in (caps or {}).items())]
    if preview:
        cmd.append("--preview")
    return run_blender(cmd, timeout=timeout, on_line=on_line)


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="meshgate gen", description="Generate a game-ready 3D asset from a description or a "
                                 "picture — as kit code written by an AI CLI, or as a neural mesh — built per quality tier.")
    ap.add_argument("description", nargs="?", help="what to make, in any language")
    ap.add_argument("--image", help="reference picture (PNG/JPG): image → 3D, or a guide for the kit code")
    ap.add_argument("--engine", default="auto", choices=["auto", "kit", "mesh"],
                    help="kit = AI CLI writes build(mg) code; mesh = neural mesh generator + refine; "
                         "auto = mesh when there is a picture and a mesh provider is ready, else kit")
    ap.add_argument("--provider", choices=list(mesh.PROVIDERS), help="mesh generator (default: the first one ready)")
    ap.add_argument("--fal-model", help="fal: fal-ai/trellis (default), fal-ai/hunyuan3d/v2, fal-ai/triposr")
    ap.add_argument("--image-provider", choices=list(mesh.images.PROVIDERS),
                    help="who draws pictures from text: codex (ChatGPT sign-in, no key), openai or fal")
    ap.add_argument("--concept", default="none", choices=["none", "sheet", "single"],
                    help="draw a concept picture from the description first: sheet = front/side/back/top turnaround "
                         "(the kit engine's AI builds from it), single = one 3/4 view (for image → 3D)")
    ap.add_argument("--mesh-cmd", help='your own generator: "cmd {image} --out {out}" ({prompt}, {out_dir} also work)')
    ap.add_argument("--mesh", help="refine an existing mesh file (GLB/OBJ/FBX/PLY/STL) — no generation")
    ap.add_argument("--turn", type=float, default=0.0, help="mesh: degrees to turn so the front faces the viewer")
    ap.add_argument("--detail", type=float, default=1.0, help="mesh: multiplier for the per-tier triangle share")
    ap.add_argument("--no-upright", action="store_true", help="mesh: keep the source tilt (no automatic standing up)")
    ap.add_argument("--vertex-srgb", action="store_true",
                    help="mesh: the file's vertex colours are picture (sRGB) values — auto for TripoSR and trimesh GLBs")
    ap.add_argument("--name", help="asset name (default: from the description or the file name)")
    ap.add_argument("--style", default="stylized", help=f"{', '.join(STYLES)} or your own words")
    ap.add_argument("--size", type=float, default=0.0, help="largest dimension in meters (default: the AI decides)")
    ap.add_argument("--tiers", default=",".join(ORDER), help="quality tiers to build; the richest one is canonical")
    ap.add_argument("--tris", help="your own triangle limits: 800 (every tier) or low=150,mid=400,high=900,pc=2000")
    ap.add_argument("--colors", default="texture", choices=["texture", "vertex"],
                    help="texture = palette / baked textures; vertex = colours in the vertices, no textures at all")
    ap.add_argument("--anim", help="kit: animation clips to make — 'open: the lid opens; idle: the lamp sways'")
    ap.add_argument("--finish", default="auto", choices=["auto", "none", "faceted", "weathered"],
                    help="kit: auto = from the style (lowpoly → faceted, realistic → weathered textures)")
    ap.add_argument("--targets", default="web,unity,godot,unreal", help="engine variants for the canonical file")
    ap.add_argument("--collision", default="none", choices=["none", "box", "convex"])
    ap.add_argument("--ai", default="claude", choices=list(ADAPTERS), help="AI CLI to use (default claude)")
    ap.add_argument("--model", help="model name passed to the AI CLI")
    ap.add_argument("--ai-cmd", help="any other CLI: reads the prompt on stdin (or {prompt_file}), prints the answer")
    ap.add_argument("--attempts", type=int, default=3, help="build → feedback → fix rounds (default 3)")
    ap.add_argument("--code", help="run this build(mg) file instead of asking an AI")
    ap.add_argument("--out-dir", help="default out/gen/<name>")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-preview", action="store_true", help="skip the preview PNG")
    ap.add_argument("--blender", help="Blender executable (default: MESHGATE_BLENDER, PATH, usual locations)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per AI answer")
    ap.add_argument("--prompt-only", action="store_true", help="print the prompt and stop")
    ap.add_argument("--list-ai", action="store_true", help="show which AI CLIs and mesh generators are ready")
    ap.add_argument("--setup", choices=["triposr", "hunyuan3d", "kimodo"],
                    help="install an optional local component: triposr (~3 GB, MIT), hunyuan3d (~10 GB), kimodo (~20 GB)")
    ap.add_argument("--events", action="store_true", help="JSON lines on stdout for the desktop app")
    return ap


def run_refine(blender: str, src: str, *, name: str, out_dir: Path, tiers: list[str], targets: str, collision: str,
               size: float, turn: float, detail: float, preview: bool, upright: bool = True, vertex_srgb: bool = False,
               timeout: int = 1800, on_line=None, cpu: bool = False, colors: str = "texture",
               caps: dict | None = None) -> tuple[dict, str]:
    cmd = [blender, "-b", "--factory-startup", "--disable-autoexec", "-P", str(REFINE), "--", "--src", src,
           "--name", name, "--out-dir", str(out_dir), "--tiers", ",".join(tiers), "--targets", targets,
           "--collision", collision, "--size", str(size or 0), "--turn", str(turn or 0), "--detail", str(detail or 1)]
    if preview:
        cmd.append("--preview")
    if not upright:
        cmd.append("--no-upright")
    if vertex_srgb:
        cmd.append("--vertex-srgb")
    if cpu:
        cmd.append("--cpu")
    cmd += ["--colors", colors, "--caps", ",".join(f"{k}={v}" for k, v in (caps or {}).items())]
    return run_blender(cmd, timeout=timeout, on_line=on_line)


def list_ready(events: bool) -> int:
    found, providers = available_ai(), mesh.status()
    if events:
        print(json.dumps({"stage": "ai", "available": found, "providers": providers, "images": mesh.images.available(),
                          "blender": find_blender()}), flush=True)
        return 0
    print("AI command-line tools (engine kit — the AI writes build code):")
    for k, path in found.items():
        state = signed_in(k) if path else None
        note = "" if state is not False else f"  — not signed in: {LOGIN_HINTS[k]}"
        print(f"  {'✓' if path and state is not False else '·'} {k:8} {path or 'not installed — ' + ADAPTERS[k]['url']}{note}")
    print("Mesh generators (engine mesh — image or text → neural mesh → refine):")
    for pid, info in providers.items():
        need = info.get("key_env") and f"set {info['key_env']}" or info.get("needs") or ""
        print(f"  {'✓' if info['ready'] else '·'} {pid:8} {info['label']} — {'ready' if info['ready'] else need}"
              f"  [{info['license']}]")
    imgs = [k for k, ok in mesh.images.available().items() if ok]
    print(f"Text → reference image: {', '.join(imgs) or 'none (set OPENAI_API_KEY or FAL_KEY)'}")
    print(f"Blender: {find_blender() or 'not found (MESHGATE_BLENDER)'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):   # Windows consoles and pipes default to cp1252; MeshGate prints ✓ and —
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    procs.install_handlers()
    events = args.events

    def say(text: str, **event):
        if events:
            print(json.dumps({"message": text, **event}, ensure_ascii=False), flush=True)
        else:
            print(text, flush=True)

    if args.setup:
        import components
        return components.COMPONENTS[args.setup].setup(log=lambda t: say(t, stage="setup"))
    if args.list_ai:
        return list_ready(events)
    if not (args.description or args.code or args.image or args.mesh):
        build_parser().print_usage()
        print("meshgate gen: give a description, --image PICTURE, --mesh FILE or --code FILE")
        return 2
    for path in (args.image, args.mesh, args.code):
        if path and not Path(path).is_file():
            print(f"meshgate gen: {path} not found")
            return 2
    stem = next((Path(x).stem for x in (args.mesh, args.image, args.code) if x), None)
    name = slug(args.name or args.description or stem or "asset", words=6 if args.name else 3)
    tiers = sorted({t.strip() for t in args.tiers.split(",") if t.strip() in ORDER}, key=ORDER.index)
    if not tiers:
        print(f"meshgate gen: --tiers must list some of {', '.join(ORDER)}")
        return 2

    try:
        args.caps_parsed = parse_caps(args.tris, tiers)
        args.finish_resolved = resolve_finish(args.finish, args.style, args.colors)
        args.anims = parse_anims(args.anim)
    except ValueError as exc:
        print(f"meshgate gen: {exc}")
        return 2
    engine = args.engine
    if args.mesh:
        engine = "mesh"
    elif args.code:
        engine = "kit"
    elif engine == "auto":
        engine = "mesh" if args.image and mesh.default_provider(True) else "kit"
    if engine == "kit" and not (args.description or args.code or args.image):
        print("meshgate gen: the kit engine needs a description or a picture")
        return 2

    if args.prompt_only:
        print(build_prompt(args.description or ("the object in the reference image" if args.image else ""), name=name,
                           style=args.style, size=args.size, tiers=tiers,
                           reference=reference_name(args.image) or ("reference.png" if args.concept == "sheet" else None),
                           caps=args.caps_parsed, reference_kind="sheet" if args.concept == "sheet" else "picture",
                           finish=args.finish_resolved, anims=args.anims))
        return 0

    blender = args.blender or find_blender()
    if not blender:
        say("Blender not found — install it (3.5+) or set MESHGATE_BLENDER.", stage="error")
        return 2
    out_dir = Path(args.out_dir or ROOT / "out" / "gen" / name).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    reference, reference_kind = None, "picture"
    if args.image:   # keep the picture next to the result: the Studio shows it, and the run is reproducible
        reference = out_dir / f"input{Path(args.image).suffix.lower() or '.png'}"
        if Path(args.image).resolve() != reference.resolve():
            shutil.copyfile(args.image, reference)
    say(f"MeshGate gen: {name} → {out_dir} (engine {engine})", stage="start", name=name, out_dir=str(out_dir),
        tiers=tiers, engine=engine)
    if args.concept != "none" and not args.image and args.description:
        kind = "single" if engine == "mesh" else args.concept
        say(f"[0] drawing a concept picture ({'turnaround sheet' if kind == 'sheet' else 'one 3/4 view'})…", stage="concept")
        try:
            concept = mesh.images.text_to_image(args.description, out_dir / "concept.png", args.image_provider,
                                                log=lambda t: say(t, stage="concept"), kind=kind, style=STYLES.get(args.style, args.style))
        except (mesh.ProviderError, OSError) as exc:
            say(f"✗ {exc}", stage="error")
            return 1
        say(f"    concept picture: {concept.name}", stage="concept")
        args.image, reference_kind = str(concept), kind
    if reference is None and args.image and args.concept != "none":
        reference = out_dir / "input.png"
        shutil.copyfile(args.image, reference)

    started = time.time()
    common = {"concept": args.concept if reference_kind != "picture" else None,
              "name": name, "description": args.description, "style": args.style, "size": args.size, "tiers": tiers,
              "colors": args.colors, "caps": args.caps_parsed, "finish": args.finish_resolved if engine == "kit" else None,
              "anims": [{"clip": n, "what": w} for n, w in args.anims] or None,
              "engine": engine, "input_image": reference.name if reference else None, "out_dir": str(out_dir)}
    if engine == "mesh":
        report, extra = generate_mesh(args, name, out_dir, tiers, blender, str(reference) if reference else None, say)
        history = [{"attempt": 1, "ok": report.get("ok", False), "problems": report.get("problems", [])}]
        summary = {**common, **extra, "ai": None, "model": None, "ok": report.get("ok", False), "attempts": history,
                   "seconds": round(time.time() - started), "report": report, "code": None}
    else:
        report, history, code = generate_kit(args, name, out_dir, tiers, blender, str(reference) if reference else None, say,
                                             reference_kind)
        summary = {**common, "ai": None if args.code else (args.ai_cmd or args.ai), "model": args.model,
                   "ok": report.get("ok", False), "attempts": history, "seconds": round(time.time() - started),
                   "report": report, "code": f"{name}.py" if report.get("ok") and code else None}
    (out_dir / "gen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    if report.get("ok"):
        files = ", ".join(report.get("files", []))
        say(f"Result: {name} is ready in {summary['seconds']} s ({engine}): {files}"
            + (f"; preview {report['preview']}" if report.get("preview") else ""), stage="done", ok=True, summary=summary)
        for a in report.get("advice", []):
            say(f"  · {a}", stage="advice")
        return 0
    say(f"Result: no clean build — logs are in {out_dir}", stage="done", ok=False, summary=summary)
    return 1


def show_tiers(report: dict, tiers: list[str], say, attempt: int = 1, streamed: bool = False) -> None:
    for tier in reversed(tiers):
        if streamed:   # the runner's own lines already went out as progress
            break
        t = report.get("tiers", {}).get(tier)
        if t:
            say(f"    {'✓' if t['within_budget'] and not t['errors'] else '✗'} {tier:12} {t['tris']:>7,} tris / "
                f"{t['max_tris'] or 0:,}  {t['file']}", stage="tier", attempt=attempt, tier=tier, data=t)
    for p in report.get("problems", []):
        say("    ✗ " + p.replace("\n", "\n      "), stage="problem", attempt=attempt, problem=p)


def srgb_vertex_colours(path: str, provider: str | None) -> bool:
    """TripoSR (and anything else written by trimesh) stores picture values in COLOR_0, which glTF defines as linear."""
    if provider and mesh.PROVIDERS[provider].INFO.get("vertex_srgb"):
        return True
    if not str(path).lower().endswith(".glb"):
        return False
    try:
        with open(path, "rb") as f:
            head = f.read(20)
            n = int.from_bytes(head[12:16], "little")
            gltf = json.loads(f.read(n))
        return "trimesh" in str(gltf.get("asset", {}).get("generator", "")).lower()
    except (OSError, ValueError):
        return False


def generate_mesh(args, name: str, out_dir: Path, tiers: list[str], blender: str, image: str | None, say):
    """Neural mesh (or a given file) → refine.py per tier. Returns (report, extra summary fields)."""
    extra = {"provider": None, "raw": None, "reference_image": None}
    if args.mesh:
        raw = str(Path(args.mesh).resolve())
        say(f"[1] refining {Path(raw).name}", stage="mesh")
    else:
        provider = args.provider or mesh.default_provider(bool(image))
        if not provider:
            msg = ("no mesh generator is ready — run `meshgate.py gen --setup triposr` (local, needs a picture) or set "
                   "MESHY_API_KEY, TRIPO_API_KEY or FAL_KEY; or use --engine kit")
            say(f"✗ {msg}", stage="error")
            return {"ok": False, "problems": [msg], "advice": []}, extra
        extra["provider"] = provider
        say(f"[1] {mesh.PROVIDERS[provider].INFO['label']}: {'picture' if image else 'description'} → 3D…", stage="mesh")
        t0 = time.time()
        try:
            got = mesh.make(provider, prompt=args.description, image=image, out_dir=out_dir,
                            log=lambda t: say(t, stage="mesh"), fal_model=args.fal_model,
                            image_provider=args.image_provider, mesh_cmd=args.mesh_cmd)
        except (mesh.ProviderError, RuntimeError, OSError) as exc:
            say(f"✗ {exc}", stage="error")
            return {"ok": False, "problems": [str(exc)], "advice": []}, extra
        raw = got["raw"]
        if got["reference"] and not image:
            extra["reference_image"] = Path(got["reference"]).name
        say(f"    raw mesh in {time.time() - t0:.0f} s: {Path(raw).name}", stage="mesh")
    extra["raw"] = Path(raw).name if Path(raw).parent == out_dir else raw
    streamed: list = []
    say(f"[1] refining for {', '.join(reversed(tiers))} in Blender (decimate, unwrap, bake)…", stage="build")
    report, log = run_refine(blender, raw, name=name, out_dir=out_dir, tiers=tiers, targets=args.targets,
                             collision=args.collision, size=args.size, turn=args.turn, detail=args.detail,
                             preview=not args.no_preview, upright=not args.no_upright,
                             vertex_srgb=args.vertex_srgb or srgb_vertex_colours(raw, extra["provider"]),
                             on_line=lambda line: (streamed.append(line), say("  " + line.strip(), stage="progress")),
                             colors=args.colors, caps=args.caps_parsed)
    if any(p.startswith("Blender stopped without a report") for p in report.get("problems", [])):
        # A GPU bake can take Blender down without a word (seen with Metal on 5.2): once more on the CPU
        say("    Blender stopped during the bake — retrying on the CPU", stage="progress")
        (out_dir / "refine.crash.log").write_text(log, encoding="utf-8")
        streamed.clear()
        report, log = run_refine(blender, raw, name=name, out_dir=out_dir, tiers=tiers, targets=args.targets,
                                 collision=args.collision, size=args.size, turn=args.turn, detail=args.detail,
                                 preview=not args.no_preview, upright=not args.no_upright,
                                 vertex_srgb=args.vertex_srgb or srgb_vertex_colours(raw, extra["provider"]),
                                 on_line=lambda line: (streamed.append(line), say("  " + line.strip(), stage="progress")),
                                 cpu=True, colors=args.colors, caps=args.caps_parsed)
        if report.get("ok"):
            report.setdefault("advice", []).append("the GPU bake crashed once; the files were baked on the CPU")
    (out_dir / "refine.blender.log").write_text(log, encoding="utf-8")
    show_tiers(report, tiers, say, streamed=bool(streamed))
    return report, extra


def generate_kit(args, name: str, out_dir: Path, tiers: list[str], blender: str, image: str | None, say,
                 reference_kind: str = "picture"):
    """AI CLI writes build(mg) → run_generated.py per tier, with the feedback loop. Returns (report, history, code)."""
    history, code, feedback, report = [], None, "", {}
    attempts = 1 if args.code else max(1, args.attempts)
    for attempt in range(1, attempts + 1):
        if args.code:
            code = Path(args.code).read_text(encoding="utf-8")
            say(f"[{attempt}] running {args.code}", stage="code", attempt=attempt)
        else:
            prompt = build_prompt(args.description or "the object in the reference image", name=name, style=args.style,
                                  size=args.size, tiers=tiers, feedback=feedback, reference=reference_name(image),
                                  caps=args.caps_parsed, reference_kind=reference_kind, finish=args.finish_resolved,
                                  anims=args.anims)
            if not args.ai_cmd and attempt == 1 and signed_in(args.ai) is False:
                msg = f"{args.ai} is not signed in — {LOGIN_HINTS.get(args.ai, 'sign in once')}"
                say(f"✗ {msg}", stage="error", attempt=attempt)
                return {"ok": False, "problems": [msg], "advice": []}, history, None
            label = args.ai_cmd or args.ai + (f" ({args.model})" if args.model else "")
            say(f"[{attempt}/{attempts}] asking {label}{' with the picture' if image else ''}…", stage="ask", attempt=attempt)
            t0 = time.time()
            try:
                answer = ask_ai(args.ai, prompt, model=args.model, ai_cmd=args.ai_cmd, timeout=args.timeout, image=image)
            except RuntimeError as exc:
                say(f"✗ {exc}", stage="error", attempt=attempt)
                return {"ok": False, "problems": [str(exc)], "advice": []}, history, None
            (out_dir / f"attempt_{attempt}.answer.md").write_text(answer, encoding="utf-8")
            code = extract_code(answer)
            say(f"    answer in {time.time() - t0:.0f} s, {len(code.splitlines())} lines of code", stage="answer",
                attempt=attempt, seconds=round(time.time() - t0))
        code_path = out_dir / f"attempt_{attempt}.py"
        code_path.write_text(code, encoding="utf-8")
        streamed: list = []
        problems = safety.check(code)
        if problems:
            report = {"ok": False, "problems": [f"safety: {p}" for p in problems], "advice": []}
        else:
            say(f"[{attempt}] building {', '.join(reversed(tiers))} in Blender…", stage="build", attempt=attempt)
            report, log = run_in_blender(blender, code_path, name=name, out_dir=out_dir, tiers=tiers,
                                         targets=args.targets, collision=args.collision, size=args.size,
                                         preview=not args.no_preview, seed=args.seed,
                                         on_line=lambda line: (streamed.append(line), say("  " + line.strip(), stage="progress", attempt=attempt)),
                                         colors=args.colors, caps=args.caps_parsed, finish=args.finish_resolved)
            (out_dir / f"attempt_{attempt}.blender.log").write_text(log, encoding="utf-8")
            missing = missing_clips(report, args.anims)
            if missing and not args.code:   # back to the AI like any other problem
                report["ok"] = False
                report.setdefault("problems", []).append(
                    f"animation clips missing: {', '.join(missing)} — make each with mg.animate(part, '<clip name>', keys) "
                    "on a separate part that is pivoted and attached")
            elif missing:
                report.setdefault("advice", []).append(f"animation clips missing: {', '.join(missing)}")
        show_tiers(report, tiers, say, attempt, streamed=bool(streamed))
        history.append({"attempt": attempt, "ok": report.get("ok", False), "problems": report.get("problems", [])})
        if report.get("ok"):
            (out_dir / f"{name}.py").write_text(code, encoding="utf-8")
            break
        feedback = feedback_block(code, report.get("problems", []), report.get("advice", []))
    return report, history, code


if __name__ == "__main__":
    sys.exit(main())
