// Before bundling: copy three.js for offline use (scripts/vendor_three.py) with whichever Python is installed.
import { spawnSync } from "node:child_process";
import { readdirSync, rmSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../..");
const script = path.join(root, "scripts", "vendor_three.py");

// Python caches must not ride along into the bundle (they would also be stale on the user's Python).
function dropCaches(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (!statSync(p).isDirectory() || name === "node_modules" || name === "target") continue;
    if (name === "__pycache__") rmSync(p, { recursive: true, force: true });
    else dropCaches(p);
  }
}
for (const d of ["core", "sources", "apps/studio", "targets/web"]) dropCaches(path.join(root, d));
const candidates = process.platform === "win32" ? [["py", "-3"], ["python"], ["python3"]] : [["python3"], ["python"]];
if (process.env.MESHGATE_PYTHON) candidates.unshift([process.env.MESHGATE_PYTHON]);
for (const [exe, ...args] of candidates) {
  const r = spawnSync(exe, [...args, script], { stdio: "inherit" });
  if (r.status === 0) {
    const runtime = spawnSync(exe, [...args, path.join(root, "scripts", "prepare_studio_bundle.py")], { stdio: "inherit" });
    if (runtime.status !== 0) process.exit(1);
    process.exit(0);
  }
}
console.error("MeshGate Studio: Python 3.9+ is needed to prepare the bundle (https://www.python.org/downloads/).");
process.exit(1);
