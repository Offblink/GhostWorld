# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — one folder, three exes, one shared `_internal/`.

    pyinstaller GhostWorld.spec --noconfirm        (or: python tools/build_exe.py)

Three entry points, because they disagree about the console:

* `GhostWorld.exe`   windowed — the launcher, and `--play` for the game.
* `GhostWorldEditor.exe` windowed — the map editor, so the release folder has a
  double-clickable editor that wears its own icon, rather than only the
  `GhostWorld.exe --editor` flag (which stays supported and is what this calls).
* `GhostWorldCLI.exe` console — `send` / `wait` / `where` / `play`. Fungi drives
  the character by spawning this as a subprocess and parsing its stdout, so
  folding it into a windowed exe would silently break that line.

All three share one `_internal/`, so the third exe costs its own bootloader and
bytecode archive, not another copy of Qt.

What the bundle has to carry beyond the modules:

* `assets/`  — both icons (window icons, and `--icon` below embeds them in the exes)
* `examples/` — the demo maps, seeded into the user's directory on first run
* `pyproject.toml` — `_paths.version_string()` reads the version from it, so the
  exe reports the version it was built from instead of stale installed metadata
"""
from pathlib import Path

ROOT = Path(SPECPATH)  # noqa: F821 — provided by PyInstaller

GAME_ICON = str(ROOT / "assets" / "ghostworld.ico")
EDITOR_ICON = str(ROOT / "assets" / "ghostworld-editor.ico")
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
editor = Analysis([str(ROOT / "tools" / "frozen" / "GhostWorldEditor.py")], **analysis_kwargs)
cli = Analysis([str(ROOT / "tools" / "frozen" / "GhostWorldCLI.py")], **analysis_kwargs)

app_pyz = PYZ(app.pure)  # noqa: F821
editor_pyz = PYZ(editor.pure)  # noqa: F821
cli_pyz = PYZ(cli.pure)  # noqa: F821

app_exe = EXE(  # noqa: F821
    app_pyz, app.scripts, [],
    exclude_binaries=True,
    name="GhostWorld",
    console=False,
    icon=GAME_ICON,
    upx=False,
)
editor_exe = EXE(  # noqa: F821
    editor_pyz, editor.scripts, [],
    exclude_binaries=True,
    name="GhostWorldEditor",
    console=False,
    icon=EDITOR_ICON,
    upx=False,
)
cli_exe = EXE(  # noqa: F821
    cli_pyz, cli.scripts, [],
    exclude_binaries=True,
    name="GhostWorldCLI",
    console=True,
    icon=GAME_ICON,
    upx=False,
)

collect = COLLECT(  # noqa: F821
    app_exe, app.binaries, app.datas,
    editor_exe, editor.binaries, editor.datas,
    cli_exe, cli.binaries, cli.datas,
    name="GhostWorld",
    upx=False,
)
