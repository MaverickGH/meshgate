**English** · [Русский](code-protection.ru.md)

# MeshGate code packaging

The repository remains public. Five Studio implementations are replaced with
loaders and native packages under `native/studio/`. Their original source stays
in the local development branch. Other published code can still be copied;
the native libraries can still be reverse engineered.

Release 0.6.11 compiles the CLI, Studio server, generation orchestration, engine
bridge and component installer into native libraries. Their distribution files
are small loaders. Generated C and debug files are excluded. Blender code,
validators and other integrations remain portable source for compatibility.

Each platform ships CPython 3.11.16 and uv. Native modules must use that runtime;
an arbitrary system Python can have an incompatible ABI. Public checkouts require the bundled CPython 3.11 runtime.

```bash
python3 scripts/vendor_three.py
python3 scripts/prepare_studio_bundle.py
python3 scripts/make_portable.py --compiled --out dist --keep out/native-portable
python3 tests/studio/test_bundle.py out/native-portable --private-runtime --blender /path/to/blender
```

Builds require pip and a C compiler. Cython 3.3.0 and setuptools 84.0.0 are
installed in a separate build environment. Desktop builds prepare resources
automatically. Temporary files stay under ignored build directories.

Portable startup: `START_WINDOWS.cmd` on Windows, `sh START.sh` on macOS/Linux.
CI checks source exclusion, startup without host Python, offline viewer and
prompt generation; Linux also runs kit generation and mesh refinement in Blender.

The old public history was reset; future development creates normal new commits.
This cannot revoke existing copies, old license permissions or cached objects.
`AGENTS.md` is a license reminder for cooperative AI tools, not access control.
Supabase activation is separate work requiring a selected project and access policy.

See [the checklist for other repositories](code-protection-other-repos.md).

Local originals are on `local-development`; never push that branch to origin.
The public main contains loaders and checked binary packages. Public CI uses
prebuilt archives; new proprietary implementations must be compiled locally
and published only as updated binaries with matching SHA-256 values.

For a clone, run `python3 scripts/build_studio_runtime.py` and then use
`apps/studio/desktop/runtime/studio/python/bin/python3.11 meshgate.py studio`
(or `python/python.exe` on Windows).
