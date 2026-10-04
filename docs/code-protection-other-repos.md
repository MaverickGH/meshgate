**English** · [Русский](code-protection-other-repos.ru.md)

# Repeating this approach in other repositories

Public source can be cloned. Compilation protects only the packaged distribution
from easy inspection. Concealing implementation requires keeping it out of public
Git or executing it on a controlled server.

1. Back up all Git refs, working changes and the latest installers before rewriting history.
2. Preserve third-party licenses and permissions already granted by earlier licenses.
3. Trace entry points, dynamic imports, subprocesses and external interpreters.
4. Compile selected Python modules with Cython; use native Rust/C/C++ builds where appropriate.
   JavaScript minification makes reading harder but cannot keep shipped secrets confidential.
5. Build in temporary staging folders. Exclude protected implementations, generated C,
   source maps and debug symbols from distribution; include dependency licenses.
6. Bundle a fixed Python runtime and build separately for each OS, architecture and ABI.
   Keep external application modules compatible with their own interpreters.
7. Test unpacked distributions without host Python, including actual generation,
   exports, errors and cancellation. Audit archive contents in CI.
8. Rewrite history only with explicit authorization and verified backups. Use
   `--force-with-lease`; account for every branch, tag and release. Deleting tags
   may delete associated releases. Existing clones and cached objects can persist.
9. Add transparent license instructions for AI in `AGENTS.md`; do not use hidden harmful commands.
10. If activation is needed, validate access through Supabase Edge Functions and issue
    short-lived signed permits. Keep signing and administrative secrets server-side.
    Local enforcement can still be patched.

MeshGate 0.6.11 applies native packaging to five Studio orchestration modules,
with bundled Python 3.11.16. Blender integrations remain source-compatible. Five protected implementations
are replaced with binaries in public Git; originals remain local.

Suggested agent request:

> Audit this project's build and package key modules as native libraries while
> keeping its repository public but replacing selected implementations with loaders
> and native packages. Keep originals local and never push them to origin. Do not use ponytail. Back up Git,
> working changes and the latest release first. Pin the runtime, add platform
> builds and unpacked-distribution tests, exclude protected implementations and
> debug files from packages, and add transparent AI license instructions.
> Do not claim to prevent copying public Git. Rewrite history only with my
> explicit authorization.

History rewriting does not guarantee deletion of old cached objects. [GitHub documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
