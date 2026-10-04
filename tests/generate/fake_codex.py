#!/usr/bin/env python3
"""Stand-in for the Codex CLI in tests: `codex exec …` like the real one.

- An image-generation task (the prompt asks for the image generation tool) → copies a picture to out.png in the -C folder.
- Any other task → answers with kit build code, written to --output-last-message (as `codex exec` does) and stdout.
  It records whether a reference picture came with -i, so tests can check the hand-off.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
args = sys.argv[1:]
if not args or args[0] != "exec":
    sys.exit("fake codex: only `exec` is supported")
prompt = args[-1] if args[-1] != "-" else sys.stdin.read()
work = Path(args[args.index("-C") + 1]) if "-C" in args else Path.cwd()
if "image generation tool" in prompt:
    kind = "sheet" if "turnaround sheet" in prompt else "single"
    shutil.copyfile(ROOT / "sources" / "generate" / "examples" / "hydrant_picture.png", work / "out.png")
    (work / "prompt.txt").write_text(prompt)
    print("out.png")
    sys.exit(0)
image = args[args.index("-i") + 1] if "-i" in args else None
code = (ROOT / "sources" / "generate" / "examples" / "fire_hydrant.py").read_text()
sheet = "turnaround sheet" in prompt
answer = f"```python\n# fake codex: reference={bool(image and Path(image).exists())} sheet_rules={sheet}\n{code}```\n"
if "--output-last-message" in args:
    Path(args[args.index("--output-last-message") + 1]).write_text(answer)
print(answer)
