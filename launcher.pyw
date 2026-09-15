"""GhostEngine Metaverse Launcher — double-click entry.

The dialog itself lives in `metaverse/launcher_gui.py`: a frozen build cannot
import a `.pyw` module, and two copies of a dialog drift. This file exists for
the Windows file association and to put the checkout root on `sys.path`.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from metaverse.launcher_gui import main  # noqa: E402  (needs ROOT on sys.path)

if __name__ == "__main__":
    main()
