#!/usr/bin/env python3
"""A stand-in AI CLI for tests: reads the prompt on stdin, answers like a model would.

First answer: code that fails in Blender (unknown part kind). Once the prompt carries MeshGate's feedback
("Your previous attempt"), it answers with the fire hydrant example — so one run exercises the whole
ask → build → feedback → fix loop without a real AI.
"""
import sys
from pathlib import Path

prompt = sys.stdin.read()
example = (Path(__file__).resolve().parents[2] / "sources" / "generate" / "examples" / "fire_hydrant.py").read_text()
if "Your previous attempt" in prompt and "part kind 'barrel'" in prompt:
    print("Fixed — `barrel` is not a kit primitive, I used lathe instead:\n\n```python\n" + example + "```")
else:
    print("```python\ndef build(mg):\n    mg.color('red', '#b3261e')\n    body = mg.part('barrel', 'red')\n"
          "    mg.join('fire_hydrant', [body])\n```")
