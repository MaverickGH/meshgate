#!/usr/bin/env python3
"""A stand-in AI CLI for tests: reads the prompt on stdin, answers like a model would.

First answer: code that fails in Blender (unknown part kind). Once the prompt carries MeshGate's feedback
("Your previous attempt"), it answers with the fire hydrant example — so one run exercises the whole
ask → build → feedback → fix loop without a real AI.
"""
import sys
from pathlib import Path

import re

prompt = sys.stdin.read()
example = (Path(__file__).resolve().parents[2] / "sources" / "generate" / "examples" / "fire_hydrant.py").read_text()
if "# Change the model" in prompt:   # an artist's change in words: apply it to the code it was given
    code = re.search(r"```python\n(.*?)```", prompt.split("# Change the model", 1)[1], re.S).group(1)
    print("Done — the body is brighter now:\n\n```python\n" + code.replace("#b3261e", "#e0452f") + "```")
elif "# Review round" in prompt:   # stage 3: the render sheet is attached; round 1 improves, round 2 is satisfied
    m = re.search(r"Reference image: (\S+)", prompt)
    seen = bool(m and Path(m.group(1)).is_file() and Path(m.group(1)).read_bytes()[:4] == b"\x89PNG")
    code = re.search(r"```python\n(.*?)```", prompt.split("# Review round", 1)[1], re.S).group(1)
    if "Review round 1 " in prompt:
        print(f"- the sheet image was {'attached' if seen else 'MISSING'}\n- the body colour is too dark\n\nMATCH: 6/10\n"
              "VIEW: at=(0, 0, 0.4) from=(1, -1, 0.5) size=0.3\n\n"
              "```python\n" + code.replace("#b3261e", "#d0342a") + "```")
    else:
        print(f"- the sheet image was {'attached' if seen else 'MISSING'}\n- close to the reference now\n\nMATCH: 9/10\n\n"
              "```python\n" + code + "```")
elif "Your previous attempt" and "part kind 'barrel'" in prompt:
    print("Fixed — `barrel` is not a kit primitive, I used lathe instead:\n\n```python\n" + example + "```")
else:
    print("```python\ndef build(mg):\n    mg.color('red', '#b3261e')\n    body = mg.part('barrel', 'red')\n"
          "    mg.join('fire_hydrant', [body])\n```")
