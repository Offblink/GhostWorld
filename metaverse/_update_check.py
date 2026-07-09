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
    """Show a popup (if PySide6 available) AND print to terminal."""
    msg = (
        f"GhostWorld 有新版本可用！\n"
        f"  当前版本: {local}\n"
        f"  最新版本: {remote}\n"
        f"  更新命令: pip cache purge && pip install --upgrade git+https://github.com/Offblink/GhostWorld.git"
    )

    # Always print to terminal
    print(f"\n{'=' * 60}\n{msg}\n{'=' * 60}\n", file=sys.stderr)

    # Try GUI popup
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        QMessageBox.information(None, "GhostWorld 更新提醒", msg)
    except Exception:
        pass


def check_update() -> None:
    """Check for updates. Skips network fetch if checked within 24h."""
    cache = _cache_path()
    now = time.time()
    local = _local_version()

    try:
        if os.path.isfile(cache):
            with open(cache) as f:
                data = json.load(f)
            if now - data.get("last_check", 0) < CHECK_INTERVAL:
                remote = data.get("remote")
                if remote and _parse_version(remote) > _parse_version(local):
                    _show_notification(local, remote)
                else:
                    print(f"[GhostWorld] 当前已是最新版本 (v{local})", file=sys.stderr)
                return
    except Exception:
        pass

    remote = _remote_version()

    try:
        with open(cache, "w") as f:
            json.dump({"last_check": now, "local": local, "remote": remote}, f)
    except Exception:
        pass

    if remote is None:
        print(f"[GhostWorld] 无法检查更新 (v{local})", file=sys.stderr)
    elif _parse_version(remote) > _parse_version(local):
        _show_notification(local, remote)
    else:
        print(f"[GhostWorld] 当前已是最新版本 (v{local})", file=sys.stderr)
