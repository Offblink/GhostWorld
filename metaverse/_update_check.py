"""Update checker — fetches latest version from GitHub and notifies if outdated.

Usage::

    from metaverse._update_check import check_update
    check_update()   # called at startup, no-op if already checked today
"""

import json
import os
import time
import sys
import urllib.request

CHECK_INTERVAL = 86400  # 24 hours between checks
REMOTE_URL = "https://raw.githubusercontent.com/Offblink/GhostWorld/master/pyproject.toml"


def _cache_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".ghostworld_update")


def _local_version() -> str:
    """Read version from installed pyproject.toml."""
    import ghostengine
    pkg_dir = os.path.dirname(os.path.abspath(ghostengine.__file__))
    toml_path = os.path.join(os.path.dirname(pkg_dir), "pyproject.toml")
    if not os.path.isfile(toml_path):
        # Fallback: scan parent directories
        d = pkg_dir
        for _ in range(5):
            d = os.path.dirname(d)
            candidate = os.path.join(d, "pyproject.toml")
            if os.path.isfile(candidate):
                toml_path = candidate
                break
    try:
        with open(toml_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "0.0.0"


def _remote_version() -> str | None:
    """Fetch latest version from GitHub raw. Returns None on failure."""
    try:
        req = urllib.request.Request(REMOTE_URL, headers={"User-Agent": "GhostWorld-updater/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            for line in resp.read().decode("utf-8").splitlines():
                line = line.strip()
                if line.startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return None


def _parse_version(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def _show_notification(local: str, remote: str) -> None:
    """Show a popup or console message about the update."""
    msg = (
        f"GhostWorld 有新版本可用！\n\n"
        f"当前版本: {local}\n"
        f"最新版本: {remote}\n\n"
        f"更新命令:\n"
        f"pip cache purge && pip install --upgrade git+https://github.com/Offblink/GhostWorld.git"
    )

    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        QMessageBox.information(None, "GhostWorld 更新提醒", msg)
        return
    except Exception:
        pass

    print(f"\n{'=' * 60}\n{msg}\n{'=' * 60}\n", file=sys.stderr)


def check_update() -> None:
    """Check for updates. Skips if checked within the last 24 hours."""
    cache = _cache_path()
    now = time.time()

    try:
        if os.path.isfile(cache):
            with open(cache) as f:
                data = json.load(f)
            if now - data.get("last_check", 0) < CHECK_INTERVAL:
                return
    except Exception:
        pass

    local = _local_version()
    remote = _remote_version()

    # Persist check time
    try:
        with open(cache, "w") as f:
            json.dump({"last_check": now, "local": local, "remote": remote}, f)
    except Exception:
        pass

    if remote and _parse_version(remote) > _parse_version(local):
        _show_notification(local, remote)
