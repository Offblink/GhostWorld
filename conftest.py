"""Make the checkout importable however pytest is invoked.

`python -m pytest` puts the working directory on sys.path; a bare `pytest` does
not, so the suite only passed for people who happened to have the package
pip-installed — the editable install hid that until it was removed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
