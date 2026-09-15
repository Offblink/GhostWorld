"""Frozen entry — the windowed exe, three faces behind one icon.

    GhostWorld.exe                    the GUI launcher (what a user double-clicks)
    GhostWorld.exe --editor [dir]     the map editor
    GhostWorld.exe --play [map.json]  straight into the game (the launcher's own hand-off)

Two exes ship together (see `GhostWorld.spec`): this one and `GhostWorldCLI.exe`.
The channel CLI must keep a console — Fungi drives the character by running it as
a subprocess and reading its stdout — so it cannot live in a `--noconsole` build.
"""
import sys

EDITOR_FLAGS = ("--editor", "-e")
PLAY_FLAGS = ("--play", "-p")
USAGE = (
    "GhostWorld.exe                 启动器（默认）\n"
    "GhostWorld.exe --editor [目录]  地图编辑器\n"
    "GhostWorld.exe --play [地图]    直接进游戏\n"
)


def _usage() -> int:
    """No console here: an unreadable command has to be shown in a dialog."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        # A QMessageBox needs a live QApplication; the instance itself is not used.
        QApplication.instance() or QApplication(sys.argv)
        QMessageBox.information(None, "GhostWorld", USAGE)
    except Exception:
        pass
    return 0


def main() -> int:
    args = sys.argv[1:]
    head = args[0] if args else ""
    if head in EDITOR_FLAGS:
        sys.argv = [sys.argv[0]] + args[1:]
        from editor import main as editor_main

        editor_main()
    elif head in PLAY_FLAGS:
        sys.argv = [sys.argv[0]] + args[1:]
        from metaverse.launch import main as play_main

        play_main()
    elif head in ("-h", "--help", "/?"):
        return _usage()
    elif head and head.startswith("-"):
        print(f"unknown option {head}\n{USAGE}", file=sys.stderr)
        return _usage()
    else:
        from metaverse.launcher_gui import main as launcher_main

        launcher_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
