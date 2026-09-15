# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — one folder, two exes, one shared `_internal/`.

    pyinstaller GhostWorld.spec --noconfirm        (or: python tools/build_exe.py)

Two entry points, because they disagree about the console:

* `GhostWorld.exe`   windowed — launcher, editor, game. A `--noconsole` build has
  no stdout, and every entry in here is GUI-only, so this is the right shape.
* `GhostWorldCLI.exe` console — `send` / `wait` / `where` / `play`. Fungi drives
  the character by spawning this as a subprocess and parsing its stdout, so
  folding it into the windowed exe would silently break that line.

What the bundle has to carry beyond the modules:

* `assets/`  — the icon (window icon, and `--icon` below embeds it in both exes)
* `examples/` — the demo maps, seeded into the user's directory on first run
* `pyproject.toml` — `_paths.version_string()` reads the version from it, so the
  exe reports the version it was built from instead of stale installed metadata
"""
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 — provided by PyInstaller

VERSION_ICON = str(ROOT / "assets" / "ghostworld.ico")
datas = [
    (str(ROOT / "pyproject.toml"), "."),
    (str(ROOT / "assets"), "assets"),
    *[(str(p), "examples") for p in sorted((ROOT / "examples").glob("*.json"))],
]

analysis_kwargs = dict(
    pathex=[str(ROOT)],
    datas=datas,
    # `pkg_resources` is imported by pygame.pkgdata (deprecated shim) and drags in
    # PyInstaller's pkg_resources runtime hook, which needs `jaraco.text` and dies
    # on import in a frozen build. pygame takes its documented `ImportError`
    # fallback (resource_exists -> False, __file__-relative path), so excluding the
    # whole tree is both smaller and correct.
    excludes=[
        "pkg_resources", "setuptools", "jaraco", "pip", "_distutils_hack",
        "pytest", "mypy", "ruff", "PIL.ImageQt",
    ],
    noarchive=False,
)

app = Analysis([str(ROOT / "tools" / "frozen" / "GhostWorld.py")], **analysis_kwargs)
cli = Analysis([str(ROOT / "tools" / "frozen" / "GhostWorldCLI.py")], **analysis_kwargs)

app_pyz = PYZ(app.pure)  # noqa: F821
cli_pyz = PYZ(cli.pure)  # noqa: F821

app_exe = EXE(  # noqa: F821
    app_pyz, app.scripts, [],
    exclude_binaries=True,
    name="GhostWorld",
    console=False,
    icon=VERSION_ICON,
    upx=False,
)
cli_exe = EXE(  # noqa: F821
    cli_pyz, cli.scripts, [],
    exclude_binaries=True,
    name="GhostWorldCLI",
    console=True,
    icon=VERSION_ICON,
    upx=False,
)

collect = COLLECT(  # noqa: F821
    app_exe, app.binaries, app.datas,
    cli_exe, cli.binaries, cli.datas,
    name="GhostWorld",
    upx=False,
)
