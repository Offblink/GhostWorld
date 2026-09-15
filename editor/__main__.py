"""`python -m editor` — the third editor entry point.

The other two are `editor.pyw` (double-click) and the `ghostworld-editor`
console script (`editor:main`); all three end in the same `main()`. Without this
file `python -m editor` fails outright with "No module named editor.__main__".
"""

from . import main

if __name__ == "__main__":
    main()
