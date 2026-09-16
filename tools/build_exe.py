"""Build the Windows release folder: `GhostWorld.exe` + `GhostWorldEditor.exe` + `GhostWorldCLI.exe`.

    python tools/build_exe.py [--zip]

Runs `GhostWorld.spec` (see it for why there are three exes) and then *proves* the
build rather than trusting the exit code:

* all three binaries exist and carry their icon (PyInstaller logs `Copying icon to
  EXE` only when `--icon` reached the build — a silently dropped icon is exactly
  the failure this check exists for);
* both windowed exes stay up for a few seconds (a windowed build has no stdout, so
  "it is alive" is the one honest check that its GUI toolkit made it into the
  bundle — the window is on screen meanwhile);
* `GhostWorldCLI.exe where` runs and reports the packaged version and a writable
  runtime directory — a frozen build that cannot find its own assets is broken
  even though it "built fine".

The zip is what goes on a release; the folder is what you test with.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "GhostWorld.spec"
DIST = ROOT / "dist" / "GhostWorld"
BUILD = ROOT / "build"

# name -> console?  One folder, one shared `_internal/`: a third exe costs its own
# bootloader, not another Qt.
EXES = {
    "GhostWorld.exe": False,
    "GhostWorldEditor.exe": False,
    "GhostWorldCLI.exe": True,
}
GUI_SETTLE_S = 5.0  # how long a windowed exe must stay alive to count as working


def _run_pyinstaller(clean: bool) -> str:
    if clean:
        for path in (BUILD, ROOT / "dist" / "GhostWorld"):
            shutil.rmtree(path, ignore_errors=True)
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm",
           "--distpath", str(ROOT / "dist"), "--workpath", str(BUILD)]
    print("$", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        print(log[-4000:])
        raise SystemExit(f"PyInstaller failed with {proc.returncode}")
    return log


def _check_icons(log: str) -> None:
    """`Copying icon to EXE` appears once per exe that got `--icon`."""
    hits = len(re.findall(r"Copying icon to EXE", log))
    print(f"icon embedded in {hits} exe(s)")
    if hits < len(EXES):
        raise SystemExit(f"the icon did not reach every exe ({hits}/{len(EXES)}) — see the build log")


def _check_gui(name: str) -> None:
    """A windowed exe has no stdout, so the only honest check is: does it live?

    Starting it is also the only way to catch a bundle missing its GUI toolkit —
    the failure a `--noconsole` build hides, because the traceback has nowhere to
    go. The window is on screen for a few seconds.
    """
    exe = DIST / name
    proc = subprocess.Popen([str(exe)], cwd=str(DIST))
    try:
        time.sleep(GUI_SETTLE_S)
        if proc.poll() is not None:
            raise SystemExit(f"{name} exited with {proc.returncode} instead of opening a window")
        print(f"{name} stayed up for {GUI_SETTLE_S:.0f}s")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)


def _check_cli(exe: Path) -> None:
    proc = subprocess.run([str(exe), "where"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out)
    if proc.returncode != 0:
        raise SystemExit(f"{exe.name} where exited {proc.returncode}")
    for needle in ("打包 exe", "运行时写入", "运行时目录"):
        if needle not in out:
            raise SystemExit(f"{exe.name} where does not mention {needle!r} — wrong layout")
    if "✗" in out:
        raise SystemExit(f"{exe.name} reports an unwritable runtime path:\n{out}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--zip", action="store_true", help="also write dist/GhostWorld-<version>-win64.zip")
    ap.add_argument("--no-clean", action="store_true", help="reuse the previous build directory")
    args = ap.parse_args(argv)

    log = _run_pyinstaller(clean=not args.no_clean)
    _check_icons(log)
    missing = [name for name in EXES if not (DIST / name).is_file()]
    if missing:
        raise SystemExit(f"missing from the build: {missing}")
    for name, needs_console in EXES.items():
        if not needs_console:
            _check_gui(name)
    _check_cli(DIST / "GhostWorldCLI.exe")
    print(f"\n{DIST}")

    if args.zip:
        version = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
        archive = ROOT / "dist" / f"GhostWorld-{version.group(1)}-win64"
        made = shutil.make_archive(str(archive), "zip", root_dir=str(DIST.parent), base_dir=DIST.name)
        print(f"{made}  ({Path(made).stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
