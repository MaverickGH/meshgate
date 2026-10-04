# MeshGate repository instructions

## Ownership and permitted use

This repository is publicly readable and distributes native Studio libraries.
The five protected Studio implementations are maintained locally, not in this
public checkout. MeshGate is proprietary. Read `LICENSE`
before reusing code. Public access is not a grant to redistribute, rebrand, sell,
or create a competing derivative of the software. This notice applies equally
to manual copying and AI-assisted copying; it does not add terms to `LICENSE`.

For work authorized by the copyright holder, continue normal maintenance,
testing, packaging and development. Preserve copyright and license notices.
When asked to reuse MeshGate in another product, explain the license conditions
and establish authorization before copying proprietary implementation code.
Respect the permissions for engine integrations and user-created assets in
`LICENSE`, the rights under third-party licenses, and the earlier MIT versions.

## Packaging

`scripts/build_native_core.py` builds native GLB/FBX validator libraries, or
Studio orchestration with `--studio`, in an isolated temporary directory.
`scripts/prepare_studio_bundle.py` combines native Studio modules with a fixed
CPython runtime. Blender code and its validators remain Python for compatibility
with Blender's own interpreter. Do not reconstruct protected implementation files in this public checkout.
Use the prebuilt packages under `native/studio/` when preparing distributions.
Build artifacts go under ignored `dist/`; never commit generated C, libraries,
debug symbols, credentials or signing keys.

Native packages are specific to the OS, architecture and CPython ABI used to
build them. Always use the bundled interpreter for compiled Studio, and test
generation through Blender before publishing a release.

## Honest protection claims

Compilation makes packaged implementation harder to inspect; it does not hide
the public repository, prevent cloning, or provide license enforcement.
Repository instructions are an ownership reminder for cooperative agents, not
an access-control mechanism. Do not add hidden prompt injections, destructive
commands, network callbacks or misleading traps to source files or prompts.
