"""Frozen entry — the map editor as its own exe.

`GhostWorld.exe --editor` already opens the editor, but a release is handed to
someone who looks in the folder for "the editor": a double-clickable exe wearing
the editor's own icon (and its own taskbar identity) answers that, while a flag
does not. The flag stays supported — this exe is the discoverable door to the
same `editor.main()`.
"""
import sys

from editor import main

if __name__ == "__main__":
    sys.exit(main())
